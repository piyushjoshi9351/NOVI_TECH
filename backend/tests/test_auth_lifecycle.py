"""First-login restrictions, credential rotation, password policy, and OAuth."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from jose import jwt
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import settings
from app.core.rate_limit import login_limiter, signup_limiter
from app.core.security import decode_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import ParentStudentLink, User
from app.schemas.auth import ParentRegisterRequest, PasswordChange
from app.schemas.parent import ParentStudentCreate
from app.services import auth as auth_service
from app.services.parent_students import create_student
from tests.conftest import auth_header

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/parent/register"
ME = "/api/v1/auth/me"
CHANGE = "/api/v1/auth/change-password"
PARENT = {"name": "Pat Parent", "email": "newparent@example.com", "password": "Parent-test-password"}


@pytest.fixture()
def temporary_student(db, parent):
    receipt = create_student(db, parent, ParentStudentCreate(name="Parent Supplied Name", email="temporary@example.com", password="Initial-student-pass"))
    return db.get(User, receipt.student_id)


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/v1/dashboard", None), ("GET", "/api/v1/chat/conversations", None),
    ("GET", "/api/v1/dna", None), ("GET", "/api/v1/passport", None),
    ("GET", "/api/v1/checkins/current", None), ("GET", "/api/v1/roadmap", None),
    ("GET", "/api/v1/memory", None), ("GET", "/api/v1/m3/students/me", None),
    ("GET", "/api/v1/onboarding/flow", None), ("GET", "/api/v1/student/parent-links", None),
    ("PATCH", ME, {"first_name": "Bypass"}), ("GET", "/api/v1/auth/links", None),
])
def test_temporary_password_blocks_normal_apis(client, temporary_student, method, path, body):
    response = client.request(method, path, json=body, headers=auth_header(temporary_student.id))
    assert response.status_code == 403 and response.json()["detail"] == "Password change required"


def test_password_change_revokes_tokens_and_unlocks_onboarding(client, db, temporary_student):
    response = client.post(LOGIN, json={"email": temporary_student.email, "password": "Initial-student-pass"})
    assert response.status_code == 200 and response.json()["user"]["must_change_password"] is True
    old = {"Authorization": f"Bearer {response.json()['access_token']}"}
    identity = client.get(ME, headers=old)
    assert identity.status_code == 200 and identity.json()["must_change_password"] is True
    response = client.post(CHANGE, json={"current_password": "Initial-student-pass", "new_password": "Independent-student-pass"}, headers=old)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok" and data["user"]["must_change_password"] is False
    assert data["user"]["onboarding_completed"] is False
    assert decode_access_token(data["access_token"])["token_version"] == 1
    db.refresh(temporary_student)
    assert temporary_student.token_version == 1 and temporary_student.must_change_password is False
    assert client.get(ME, headers=old).status_code == 401
    assert client.get(ME, headers=auth_header(temporary_student.id)).status_code == 401
    fresh = {"Authorization": f"Bearer {data['access_token']}"}
    assert client.get(ME, headers=fresh).status_code == 200
    state = client.get("/api/v1/onboarding/flow", headers=fresh)
    assert state.status_code == 200 and state.json()["current"]["prefill"] == "Parent Supplied Name"
    assert client.post(LOGIN, json={"email": temporary_student.email, "password": "Initial-student-pass"}).status_code == 401
    logged_in = client.post(LOGIN, json={"email": temporary_student.email, "password": "Independent-student-pass"})
    assert decode_access_token(logged_in.json()["access_token"])["token_version"] == 1


@pytest.mark.parametrize("current,new", [("wrong", "Independent-student-pass"), ("Initial-student-pass", "Initial-student-pass")])
def test_failed_password_change_preserves_flags(client, db, temporary_student, current, new):
    assert client.post(CHANGE, json={"current_password": current, "new_password": new}, headers=auth_header(temporary_student.id)).status_code == 400
    db.refresh(temporary_student)
    assert temporary_student.must_change_password and temporary_student.token_version == 0


def test_legacy_password_login_and_parent_rotation(client, db, parent):
    parent.password_hash = hash_password("oldpass")
    db.commit()
    assert client.post(LOGIN, json={"email": parent.email, "password": "oldpass"}).status_code == 200
    old = auth_header(parent.id, "parent")
    response = client.post(CHANGE, json={"current_password": "oldpass", "new_password": "Independent-parent-pass"}, headers=old)
    assert response.status_code == 200 and client.get(ME, headers=old).status_code == 401
    assert client.get(ME, headers={"Authorization": f"Bearer {response.json()['access_token']}"}).status_code == 200


@pytest.mark.parametrize("version", ["0", -1, True, 0.0, 99])
def test_invalid_token_versions_rejected(client, user, version):
    token = jwt.encode({"sub": str(user.id), "token_version": version, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_pre_refactor_jwt_only_works_at_version_zero(client, db, user):
    token = jwt.encode({"sub": str(user.id), "role": "student", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(ME, headers=headers).status_code == 200
    user.token_version = 1
    db.commit()
    assert client.get(ME, headers=headers).status_code == 401


@pytest.mark.parametrize("password", ["short", "x" * 73, "é" * 37])
def test_new_password_policy_shared(password):
    for schema, body in (
        (ParentRegisterRequest, {**PARENT, "password": password}),
        (ParentStudentCreate, {**PARENT, "password": password}),
        (PasswordChange, {"current_password": "oldpass", "new_password": password}),
    ):
        with pytest.raises(ValidationError):
            schema(**body)


def test_multibyte_password_at_exact_limit(client):
    assert client.post(REGISTER, json={**PARENT, "password": "é" * 36}).status_code == 201


def test_auth_validation_does_not_echo_credentials(client, user):
    for path, body in ((REGISTER, {**PARENT, "password": "short"}), (LOGIN, {"email": "invalid", "password": PARENT["password"]}), (CHANGE, {"current_password": "oldpass", "new_password": "short"})):
        response = client.post(path, json=body, headers=auth_header(user.id))
        assert response.status_code == 422 and PARENT["password"] not in response.text
        assert all("input" not in error for error in response.json()["detail"])


def test_login_and_signup_rate_limits(client, monkeypatch):
    monkeypatch.setattr(login_limiter, "limit", 1)
    monkeypatch.setattr(signup_limiter, "limit", 1)
    body = {"email": "unknown@example.com", "password": "wrong"}
    assert client.post(LOGIN, json=body).status_code == 401
    assert client.post(LOGIN, json=body).status_code == 429
    assert client.post(REGISTER, json=PARENT).status_code == 201
    assert client.post(REGISTER, json={**PARENT, "email": "second@example.com"}).status_code == 429
    assert client.post("/api/v1/auth/signup", json=PARENT).status_code == 429


@pytest.mark.parametrize("intent", ["student", "", "admin"])
def test_google_unknown_student_rejected(db, intent):
    with pytest.raises(HTTPException) as exc:
        auth_service._upsert_google_user("unknown@example.com", "Unknown", None, db, intent)
    assert exc.value.status_code == 403
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_google_parent_signup_existing_student_login(db, user):
    parent, is_new = auth_service._upsert_google_user("google-parent@example.com", "Pat Parent", None, db, "parent")
    assert is_new and parent.role == UserRole.PARENT and parent.needs_child_setup
    existing, is_new = auth_service._upsert_google_user(user.email, "Ignored", None, db, "parent")
    assert not is_new and existing.id == user.id and existing.role == UserRole.STUDENT
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 0


def test_google_verified_email_cannot_bypass_creation(db, monkeypatch):
    monkeypatch.setattr(auth_service, "_exchange_google_code", AsyncMock(return_value={"id_token": "dummy"}))
    monkeypatch.setattr(auth_service, "_verify_google_id_token", AsyncMock(return_value={"email": "unknown@example.com", "email_verified": True}))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_service.google_login("dummy", db, "student"))
    assert exc.value.status_code == 403


def test_google_disabled_account_rejected(db, user):
    user.is_active = False
    db.commit()
    with pytest.raises(HTTPException) as exc:
        auth_service._upsert_google_user(user.email, "Ignored", None, db)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("intent", ["student", "parent"])
def test_google_callback_retires_temporary_credentials(client, db, temporary_student, monkeypatch, intent):
    temporary_student.token_version = 3
    db.commit()
    old_hash = temporary_student.password_hash
    old_headers = auth_header(temporary_student.id, token_version=3)
    monkeypatch.setattr(auth_service, "google_is_configured", lambda: True)
    monkeypatch.setattr(auth_service, "_exchange_google_code", AsyncMock(return_value={"id_token": "dummy"}))
    monkeypatch.setattr(auth_service, "_verify_google_id_token", AsyncMock(return_value={"email": temporary_student.email, "email_verified": True, "picture": "https://example.com/avatar.png"}))
    state = auth_service.build_oauth_state("nonce", "/login", intent)
    client.cookies.set("google_oauth_state", "nonce")
    response = client.get("/api/v1/auth/google/callback", params={"code": "dummy", "state": state}, follow_redirects=False)
    assert response.status_code == 302
    token = parse_qs(urlsplit(response.headers["location"]).query)["google_token"][0]
    assert decode_access_token(token)["token_version"] == 4
    db.refresh(temporary_student)
    assert temporary_student.must_change_password is False and temporary_student.token_version == 4
    assert temporary_student.has_local_password is False and temporary_student.first_login_at is not None
    assert temporary_student.password_hash != old_hash
    assert not verify_password("Initial-student-pass", temporary_student.password_hash)
    assert temporary_student.role == UserRole.STUDENT and temporary_student.created_by_parent_id is not None
    assert client.get(ME, headers=old_headers).status_code == 401
    assert client.get(ME, headers=auth_header(temporary_student.id)).status_code == 401
    assert client.post(LOGIN, json={"email": temporary_student.email, "password": "Initial-student-pass"}).status_code == 401
    headers = {"Authorization": f"Bearer {token}"}
    identity = client.get(ME, headers=headers).json()
    assert identity["must_change_password"] is False and identity["has_local_password"] is False
    assert client.get("/api/v1/onboarding/flow", headers=headers).status_code == 200
    # A later Google login must not keep invalidating the student's sessions.
    auth_service._upsert_google_user(temporary_student.email, "Ignored", None, db, intent)
    assert temporary_student.token_version == 4
    assert "Initial-student-pass" not in response.text


def test_google_takeover_rolls_back_credentials_on_commit_failure(db, temporary_student, monkeypatch):
    original_hash = temporary_student.password_hash
    monkeypatch.setattr(db, "commit", Mock(side_effect=RuntimeError("commit failed")))
    with pytest.raises(RuntimeError, match="commit failed"):
        auth_service._upsert_google_user(temporary_student.email, "Ignored", "https://example.com/new.png", db)
    db.refresh(temporary_student)
    assert temporary_student.password_hash == original_hash
    assert temporary_student.must_change_password is True and temporary_student.token_version == 0
    assert temporary_student.avatar is None


def test_unverified_google_login_preserves_temporary_credentials(db, temporary_student, monkeypatch):
    original_hash = temporary_student.password_hash
    monkeypatch.setattr(auth_service, "_exchange_google_code", AsyncMock(return_value={"id_token": "dummy"}))
    monkeypatch.setattr(auth_service, "_verify_google_id_token", AsyncMock(return_value={"email": temporary_student.email, "email_verified": False}))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_service.google_login("dummy", db))
    assert exc.value.status_code == 401
    db.refresh(temporary_student)
    assert temporary_student.password_hash == original_hash
    assert temporary_student.must_change_password is True and temporary_student.token_version == 0
