"""Parent provisioning, credential safety, transactions, and abuse limits."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.parent import parent_creation_limiter, student_creation_limiter
from app.core.database import Base
from app.core.security import verify_password
from app.models.enums import LinkStatus, UserRole
from app.models.user import ParentStudentLink, User
from app.schemas.parent import ParentStudentCreate
from app.services import parent_students
from tests.conftest import auth_header

PATH = "/api/v1/parent/students"
BODY = {"name": "Child Name", "email": "child@example.com", "password": "Initial-child-password"}


def test_only_authenticated_parents_can_create(client, user):
    assert client.post(PATH, json=BODY).status_code == 401
    # A forged role claim cannot turn the database student into a parent.
    assert client.post(PATH, json=BODY, headers=auth_header(user.id, "parent")).status_code == 403


@pytest.mark.parametrize("extra", [{"parent_id": 999}, {"role": "parent"}, {"scopes": {"memory": True}}])
def test_owner_role_and_scopes_cannot_be_supplied(client, parent, extra):
    response = client.post(PATH, json={**BODY, **extra}, headers=auth_header(parent.id, "parent"))
    assert response.status_code == 422
    assert BODY["password"] not in response.text


def test_creation_flags_active_link_and_unchanged_parent_session(client, db, parent):
    headers = auth_header(parent.id, "parent")
    response = client.post(PATH, json={**BODY, "name": "  Child Name  ", "email": " CHILD@EXAMPLE.COM "}, headers=headers)
    assert response.status_code == 201
    receipt = response.json()
    assert set(receipt) == {"student_id", "link_id", "name", "status", "scopes", "activated_at"}
    assert receipt["status"] == "active" and receipt["scopes"] == ["basic"]
    assert receipt["name"] == "Child Name"
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers
    assert BODY["password"] not in response.text
    child = db.get(User, receipt["student_id"])
    link = db.get(ParentStudentLink, receipt["link_id"])
    assert child.email == "child@example.com" and child.role == UserRole.STUDENT
    assert child.must_change_password is True and child.token_version == 0
    assert child.created_by_parent_id == parent.id
    assert verify_password(BODY["password"], child.password_hash)
    assert child.letta_agent_id is None
    assert link.parent_id == parent.id and link.student_id == child.id
    assert link.status == LinkStatus.ACTIVE and link.scopes == {"basic": True}
    assert link.activation_source == "parent_created" and link.activated_at is not None
    assert link.confirmed_at is None and link.revoked_at is None
    assert link.invited_email is None and link.invite_token_hash is None
    assert client.get("/api/v1/auth/me", headers=headers).json()["id"] == parent.id
    assert client.get(f"{PATH}/{child.id}/overview", headers=headers).status_code == 200
    assert client.get(f"{PATH}/{child.id}/insights", headers=headers).json()["passport_items"] == []
    assert client.get(f"{PATH}/{child.id}/memory", headers=headers).json()["growth"] is None


def test_parent_can_create_multiple_children(client, db, parent):
    for email in ("one@example.com", "two@example.com"):
        assert client.post(PATH, json={**BODY, "email": email}, headers=auth_header(parent.id, "parent")).status_code == 201
    assert db.scalar(select(func.count()).select_from(ParentStudentLink).where(ParentStudentLink.parent_id == parent.id)) == 2


@pytest.mark.parametrize("existing_role", [UserRole.STUDENT, UserRole.PARENT])
def test_existing_account_gets_409_without_changes(client, db, parent, existing_role):
    existing = User(email=BODY["email"], password_hash="unchanged", role=existing_role, first_name="Original")
    db.add(existing)
    db.commit()
    response = client.post(PATH, json=BODY, headers=auth_header(parent.id, "parent"))
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    db.refresh(existing)
    assert existing.password_hash == "unchanged" and existing.first_name == "Original"
    assert existing.role == existing_role and existing.created_by_parent_id is None
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 0


def test_duplicate_retry_does_not_reset_initial_password(client, db, parent):
    headers = auth_header(parent.id, "parent")
    first = client.post(PATH, json=BODY, headers=headers).json()
    response = client.post(PATH, json={**BODY, "password": "A-different-password"}, headers=headers)
    assert response.status_code == 409
    assert verify_password(BODY["password"], db.get(User, first["student_id"]).password_hash)
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 1


def test_child_email_cannot_equal_parent_email(client, parent):
    response = client.post(PATH, json={**BODY, "email": parent.email.upper()}, headers=auth_header(parent.id, "parent"))
    assert response.status_code == 400


@pytest.mark.parametrize("failure", ["link", "commit"])
def test_creation_rolls_back_completely(db, parent, monkeypatch, failure):
    def reject_link(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO PARENT_STUDENT_LINKS"):
            raise RuntimeError("injected link failure")

    if failure == "link":
        event.listen(db.bind, "before_cursor_execute", reject_link)
    else:
        monkeypatch.setattr(db, "commit", Mock(side_effect=RuntimeError("injected commit failure")))
    try:
        with pytest.raises(RuntimeError, match="injected"):
            parent_students.create_student(db, parent, ParentStudentCreate(**BODY))
    finally:
        if failure == "link":
            event.remove(db.bind, "before_cursor_execute", reject_link)
    assert db.scalar(select(User.id).where(User.email == BODY["email"])) is None
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 0


def test_success_commits_once(db, parent, monkeypatch):
    commit = Mock(wraps=db.commit)
    monkeypatch.setattr(db, "commit", commit)
    parent_students.create_student(db, parent, ParentStudentCreate(**BODY))
    assert commit.call_count == 1


def test_invitation_only_legacy_link_is_untouched(client, db, parent, other_parent):
    invitation = ParentStudentLink(parent_id=other_parent.id, invited_email=BODY["email"], status=LinkStatus.PENDING, scopes={"basic": True, "memory": True}, expires_at=datetime(2020, 1, 1))
    db.add(invitation)
    db.commit()
    assert client.post(PATH, json=BODY, headers=auth_header(parent.id, "parent")).status_code == 201
    db.refresh(invitation)
    assert invitation.student_id is None and invitation.status == LinkStatus.PENDING
    assert invitation.scopes == {"basic": True, "memory": True}
    assert invitation.expires_at == datetime(2020, 1, 1)


@pytest.mark.parametrize("payload", [
    {**BODY, "password": "short"}, {**BODY, "password": "x" * 73},
    {**BODY, "password": "é" * 37}, {**BODY, "password": "\ud800" * 8},
    {**BODY, "name": "   "}, [BODY],
])
def test_invalid_requests_never_echo_credentials(client, parent, payload):
    response = client.post(PATH, content=json.dumps(payload, ensure_ascii=True), headers={**auth_header(parent.id, "parent"), "Content-Type": "application/json"})
    assert response.status_code == 422
    assert BODY["password"] not in response.text
    assert all(set(error) == {"type", "loc", "msg"} for error in response.json()["detail"])


def test_creation_limited_per_ip(client, parent, monkeypatch):
    monkeypatch.setattr(student_creation_limiter, "limit", 1)
    headers = auth_header(parent.id, "parent")
    assert client.post(PATH, json=BODY, headers=headers).status_code == 201
    response = client.post(PATH, json={**BODY, "email": "two@example.com"}, headers=headers)
    assert response.status_code == 429 and int(response.headers["retry-after"]) > 0


def test_parent_limit_survives_ip_changes(client, parent, monkeypatch):
    monkeypatch.setattr(parent_creation_limiter, "limit", 1)
    first_ip = TestClient(client.app, client=("198.51.100.1", 1000))
    second_ip = TestClient(client.app, client=("198.51.100.2", 1000))
    headers = auth_header(parent.id, "parent")
    assert first_ip.post(PATH, json=BODY, headers=headers).status_code == 201
    assert second_ip.post(PATH, json={**BODY, "email": "two@example.com"}, headers=headers).status_code == 429


def test_parent_limit_does_not_use_request_body_or_another_parent(client, parent, other_parent, monkeypatch):
    monkeypatch.setattr(parent_creation_limiter, "limit", 1)
    assert client.post(PATH, json=BODY, headers=auth_header(parent.id, "parent")).status_code == 201
    assert client.post(PATH, json={**BODY, "email": "other-child@example.com"}, headers=auth_header(other_parent.id, "parent")).status_code == 201


def test_proxy_client_ip_and_untrusted_forwarding_headers(client, parent, monkeypatch):
    monkeypatch.setattr(student_creation_limiter, "limit", 1)
    monkeypatch.setattr(parent_creation_limiter, "limit", 100)
    proxied = ProxyHeadersMiddleware(client.app, trusted_hosts=["10.0.0.0/24"])
    trusted = TestClient(proxied, client=("10.0.0.2", 1000))
    headers = auth_header(parent.id, "parent")
    assert trusted.post(PATH, json=BODY, headers={**headers, "X-Forwarded-For": "198.51.100.10"}).status_code == 201
    assert trusted.post(PATH, json=BODY, headers={**headers, "X-Forwarded-For": "198.51.100.11"}).status_code == 409
    assert trusted.post(PATH, json=BODY, headers={**headers, "X-Forwarded-For": "198.51.100.10"}).status_code == 429
    untrusted = TestClient(proxied, client=("203.0.113.1", 1000))
    assert untrusted.post(PATH, json=BODY, headers={**headers, "X-Forwarded-For": "192.0.2.1"}).status_code == 409
    assert untrusted.post(PATH, json=BODY, headers={**headers, "X-Forwarded-For": "192.0.2.2"}).status_code == 429


def test_simultaneous_duplicate_inserts_create_exactly_one_family(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'race.sqlite'}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            parent = User(email="parent@example.com", password_hash="unused", role=UserRole.PARENT)
            db.add(parent)
            db.commit()
            parent_id = parent.id
        barrier = Barrier(2)

        def synchronize(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT INTO USERS"):
                barrier.wait(timeout=10)

        event.listen(engine, "before_cursor_execute", synchronize)

        def attempt(_):
            with Session(engine, autoflush=False) as db:
                parent = db.get(User, parent_id)
                try:
                    parent_students.create_student(db, parent, ParentStudentCreate(**BODY))
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt, range(2))) == [201, 409]
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(User).where(User.email == BODY["email"])) == 1
            assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 1
    finally:
        engine.dispose()
