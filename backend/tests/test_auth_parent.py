"""Prompt 1 auth surface: parent registration, expected_role, /auth/me, Google state."""

import pytest
from fastapi import HTTPException

from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, ParentRegisterRequest, SignupRequest
from app.services import auth as auth_service
from tests.conftest import auth_header


# ------------------------------------------------------------------ parent register
PARENT_BODY = {"name": "Pat Parent", "email": "newparent@example.com", "password": "Parent-test-pass"}


def test_register_parent_fixes_the_role_server_side(db):
    user = auth_service.register_parent(ParentRegisterRequest(**PARENT_BODY), db)
    assert user.role == UserRole.PARENT
    assert user.needs_child_setup is True
    assert user.letta_agent_id is None


@pytest.mark.parametrize("extra", [{"role": "parent"}, {"student_email": "kid@example.com"}])
def test_register_parent_rejects_role_and_old_child_email(extra):
    with pytest.raises(ValueError):
        ParentRegisterRequest(**PARENT_BODY, **extra)


@pytest.mark.parametrize("fixture_name", ["user", "parent"])
def test_register_parent_rejects_existing_email(db, request, fixture_name):
    existing = request.getfixturevalue(fixture_name)
    old_hash = existing.password_hash
    with pytest.raises(HTTPException) as exc:
        auth_service.register_parent(ParentRegisterRequest(**{**PARENT_BODY, "email": existing.email}), db)
    assert exc.value.status_code == 409
    db.refresh(existing)
    assert existing.password_hash == old_hash


def test_register_parent_endpoint_authenticates_without_invitation(client, db):
    from sqlalchemy import func, select
    from app.core.security import decode_access_token, verify_password
    from app.models.user import ParentStudentLink, User
    r = client.post("/api/v1/auth/parent/register", json=PARENT_BODY)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"access_token", "token_type", "user"}
    assert body["user"]["role"] == "parent" and body["user"]["needs_child_setup"] is True
    assert body["user"]["must_change_password"] is False
    assert decode_access_token(body["access_token"])["token_version"] == 0
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["id"] == body["user"]["id"]
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 0
    assert verify_password(PARENT_BODY["password"], db.get(User, body["user"]["id"]).password_hash)
    assert PARENT_BODY["password"] not in r.text


def test_register_parent_normalizes_email(client):
    created = client.post("/api/v1/auth/parent/register", json={**PARENT_BODY, "email": "MixedCase@Example.com"})
    assert created.status_code == 201
    assert client.post("/api/v1/auth/login", json={"email": "mixedcase@example.com", "password": PARENT_BODY["password"]}).status_code == 200


# ------------------------------------------------------------------ expected_role
def test_login_without_expected_role_still_works(db, user):
    user.password_hash = _hash("hunter2!")
    db.commit()
    db.refresh(user)
    assert auth_service.login(LoginRequest(email=user.email, password="hunter2!"), db).id == user.id


def test_expected_role_blocks_a_parent_on_the_student_form(db, parent):
    parent.password_hash = _hash("hunter2!")
    db.commit()
    db.refresh(parent)
    with pytest.raises(HTTPException) as exc:
        auth_service.login(
            LoginRequest(email=parent.email, password="hunter2!", expected_role="student"), db
        )
    assert exc.value.status_code == 403
    assert "parent" in str(exc.value.detail).lower()


def test_expected_role_allows_a_parent_on_the_parent_form(db, parent):
    parent.password_hash = _hash("hunter2!")
    db.commit()
    db.refresh(parent)
    got = auth_service.login(
        LoginRequest(email=parent.email, password="hunter2!", expected_role="parent"), db
    )
    assert got.id == parent.id


def test_wrong_password_still_401_not_403(db, user):
    with pytest.raises(HTTPException) as exc:
        auth_service.login(
            LoginRequest(email=user.email, password="wrong", expected_role="student"), db
        )
    assert exc.value.status_code == 401


def test_expected_role_is_validated_by_the_schema():
    with pytest.raises(Exception):
        LoginRequest(email="a@b.test", password="x", expected_role="admin")


# ------------------------------------------------------------------ /auth/me
def test_me_returns_identity_from_the_database(client, user):
    r = client.get("/api/v1/auth/me", headers=auth_header(user.id, "student"))
    assert r.status_code == 200
    assert r.json()["email"] == user.email
    assert r.json()["role"] == "student"
    assert r.json()["name"] == "Test Student"


def test_me_ignores_the_role_claim_in_the_token(client, parent):
    """A parent token claiming role=student must still report 'parent'."""
    r = client.get("/api/v1/auth/me", headers=auth_header(parent.id, "student"))
    assert r.json()["role"] == "parent"


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_does_not_leak_sensitive_fields(client, user):
    body = client.get("/api/v1/auth/me", headers=auth_header(user.id, "student")).json()
    assert "password_hash" not in body
    assert "letta_agent_id" not in body


def test_me_rejects_a_forged_non_numeric_sub(client):
    from app.core.security import create_access_token

    token = create_access_token("not-a-number", "student")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401, "must be a clean 401, not a 500"


# ------------------------------------------------------------------ Google state
def test_oauth_state_round_trips():
    state = auth_service.build_oauth_state("nonce123", "/signup", "parent")
    assert auth_service.verify_oauth_state(state) == ("nonce123", "parent", "/signup")


def test_oauth_state_rejects_a_tampered_intent():
    state = auth_service.build_oauth_state("nonce123", "/signup", "student")
    tampered = state.replace(":student:", ":parent:")
    assert auth_service.verify_oauth_state(tampered) is None


def test_oauth_state_rejects_a_tampered_path():
    state = auth_service.build_oauth_state("n", "/signup", "student")
    assert auth_service.verify_oauth_state(state.replace("/signup", "/evil")) is None


def test_oauth_state_rejects_a_tampered_nonce():
    state = auth_service.build_oauth_state("n", "/signup", "student")
    assert auth_service.verify_oauth_state(state.replace("n:", "x:", 1)) is None


def test_oauth_state_rejects_garbage():
    assert auth_service.verify_oauth_state("nonsense") is None
    assert auth_service.verify_oauth_state("") is None
    assert auth_service.verify_oauth_state("a:b:c") is None


def test_oauth_state_does_not_leak_the_secret():
    state = auth_service.build_oauth_state("n", "/signup", "student")
    from app.core.config import settings

    assert settings.SECRET_KEY not in state


def test_google_url_carries_the_signed_state():
    from app.core.config import settings

    settings.GOOGLE_CLIENT_ID = "cid"
    try:
        url = auth_service.build_google_authorize_url("n", "/signup", "parent")
        assert "state=" in url
        assert "parent" in url
    finally:
        settings.GOOGLE_CLIENT_ID = ""


# ------------------------------------------------------------------ retired signup
@pytest.mark.parametrize("role", [None, "student", "parent", "admin"])
def test_public_signup_cannot_create_accounts(client, db, role):
    from sqlalchemy import func, select
    from app.models.user import User
    body = {"email": "new@example.com", "password": "Student-test-pass"}
    if role is not None:
        body["role"] = role
    assert client.post("/api/v1/auth/signup", json=body).status_code == 403
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_retired_signup_service_cannot_create_accounts(db):
    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_service.signup(SignupRequest(email="new@example.com", password="Student-test-pass"), db))
    assert exc.value.status_code == 403


def test_login_does_not_claim_invitation_only_legacy_rows(db, parent, user):
    from app.models.user import ParentStudentLink
    invitation = ParentStudentLink(parent_id=parent.id, invited_email=user.email, scopes={"basic": True})
    db.add(invitation)
    user.password_hash = _hash("hunter2!")
    db.commit()
    auth_service.login(LoginRequest(email=user.email, password="hunter2!"), db)
    db.refresh(invitation)
    assert invitation.student_id is None and invitation.status.value == "pending"


def _hash(password):
    from app.core.security import hash_password
    return hash_password(password)
