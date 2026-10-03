"""Prompt 1 auth surface: parent registration, expected_role, /auth/me, Google state."""

import pytest
from fastapi import HTTPException

from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, ParentRegisterRequest, SignupRequest
from app.services import auth as auth_service
from tests.conftest import auth_header


# ------------------------------------------------------------------ parent register
def test_register_parent_fixes_the_role_server_side(db):
    data = ParentRegisterRequest(
        email="newparent@example.com", password="hunter2!", student_email="kid@example.com"
    )
    user, link = auth_service.register_parent(data, db)
    assert user.role == UserRole.PARENT


def test_register_parent_has_no_role_field_on_the_body():
    """A client cannot pick the role: the field does not exist on the schema."""
    assert "role" not in ParentRegisterRequest.model_fields
    with pytest.raises(Exception):
        ParentRegisterRequest(
            email="x@example.com", password="hunter2!",
            student_email="kid@example.com", role="parent",
        )


def test_register_parent_creates_a_pending_link(db, user):
    data = ParentRegisterRequest(
        email="p2@example.com", password="hunter2!", student_email=user.email
    )
    _parent, link = auth_service.register_parent(data, db)
    assert link.status.value == "pending"
    assert link.student_id == user.id


def test_register_parent_rejects_an_existing_student_email(db, user):
    data = ParentRegisterRequest(
        email=user.email, password="hunter2!", student_email="other@example.com"
    )
    with pytest.raises(HTTPException) as exc:
        auth_service.register_parent(data, db)
    assert exc.value.status_code == 400
    assert "student" in str(exc.value.detail).lower()


def test_register_parent_rejects_an_existing_parent_email(db, parent):
    data = ParentRegisterRequest(
        email=parent.email, password="hunter2!", student_email="kid@example.com"
    )
    with pytest.raises(HTTPException) as exc:
        auth_service.register_parent(data, db)
    assert exc.value.status_code == 400


def test_parent_has_no_letta_agent(db):
    data = ParentRegisterRequest(
        email="p3@example.com", password="hunter2!", student_email="kid@example.com"
    )
    user, _link = auth_service.register_parent(data, db)
    assert user.letta_agent_id is None


def test_register_parent_hashes_the_password(db):
    from app.core import security

    data = ParentRegisterRequest(
        email="p4@example.com", password="hunter2!", student_email="kid@example.com"
    )
    user, _link = auth_service.register_parent(data, db)
    assert user.password_hash != "hunter2!"
    assert security.verify_password("hunter2!", user.password_hash)


def test_register_parent_endpoint(client):
    r = client.post("/api/v1/auth/parent/register", json={
        "email": "ep@example.com",
        "password": "hunter2!",
        "name": "Eve",
        "student_email": "kid@example.com",
    })
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "parent"
    assert "request" in r.json()["message"]


def test_register_parent_normalizes_email(client):
    created = client.post("/api/v1/auth/parent/register", json={
        "email": "MixedCase@Example.com",
        "password": "hunter2!",
        "student_email": "kid@example.com",
    })
    assert created.status_code == 201, created.text
    r = client.post("/api/v1/auth/login", json={"email": "mixedcase@example.com", "password": "hunter2!"})
    assert r.status_code == 200, r.text


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


# ------------------------------------------------------------------ invitation hooks
def test_password_login_resolves_a_pending_invitation(db, parent, user):
    from app.services import parent_links

    invitation = parent_links.create_pending_link(db, parent, user.email)
    invitation.student_id = None
    db.commit()

    user.password_hash = _hash("hunter2!")
    db.commit()
    db.refresh(user)

    auth_service.login(LoginRequest(email=user.email, password="hunter2!"), db)

    db.refresh(invitation)
    assert invitation.student_id == user.id
    assert invitation.status.value == "pending"


def test_signup_resolves_a_pending_invitation(db, parent):
    import asyncio

    from sqlalchemy import select

    from app.models.user import ParentStudentLink
    from app.services import parent_links

    parent_links.create_pending_link(db, parent, "later@example.com")
    data = SignupRequest(email="later@example.com", password="hunter2!", role="student")
    asyncio.run(auth_service.signup(data, db))

    link = db.scalar(
        select(ParentStudentLink).where(ParentStudentLink.invited_email == "later@example.com")
    )
    assert link.student_id is not None
    assert link.status.value == "pending"


def test_parent_login_does_not_resolve_invitations(db, parent):
    from app.services import parent_links

    invitation = parent_links.create_pending_link(db, parent, "stranger@example.com")
    parent.password_hash = _hash("hunter2!")
    db.commit()
    db.refresh(parent)

    auth_service.login(LoginRequest(email=parent.email, password="hunter2!"), db)
    db.refresh(invitation)
    assert invitation.student_id is None


def _hash(password: str) -> str:
    from app.core import security

    return security.hash_password(password)
# ------------------------------------------------- signup is student-only
def test_signup_schema_rejects_role_parent():
    """A client cannot create a parent through the generic signup route."""
    with pytest.raises(ValueError) as exc:
        SignupRequest(email="s@example.com", password="hunter2!", role="parent")
    assert "parent/register" in str(exc.value)


@pytest.mark.parametrize("body", [
    {"email": "plain@example.com", "password": "hunter2!"},
    {"email": "explicit@example.com", "password": "hunter2!", "role": "student"},
])
def test_signup_without_a_role_still_works(db, body):
    import asyncio

    user = asyncio.run(auth_service.signup(SignupRequest(**body), db))
    assert user.role == UserRole.STUDENT


def test_signup_endpoint_rejects_role_parent(client, db):
    """End-to-end: the HTTP surface refuses to mint a parent."""
    r = client.post("/api/v1/auth/signup", json={
        "email": "sneaky@example.com", "password": "hunter2!", "role": "parent",
    })
    assert r.status_code == 422
    assert _email_taken(db, "sneaky@example.com") is False


def test_signup_endpoint_rejects_other_roles(client, db):
    for bogus in ("admin", "teacher", "Parent", "PARENT"):
        r = client.post("/api/v1/auth/signup", json={
            "email": "sneaky@example.com", "password": "hunter2!", "role": bogus,
        })
        assert r.status_code == 422, bogus
    assert _email_taken(db, "sneaky@example.com") is False


def _email_taken(db, email: str) -> bool:
    from sqlalchemy import select

    from app.models.user import User

    return db.scalar(select(User).where(User.email == email)) is not None


def test_signup_endpoint_still_accepts_students(client):
    r = client.post("/api/v1/auth/signup", json={
        "email": "okay@example.com", "password": "hunter2!", "role": "student",
    })
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "student"


def test_signup_with_no_role_field_still_works(client):
    r = client.post("/api/v1/auth/signup", json={
        "email": "norole@example.com", "password": "hunter2!",
    })
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "student"


def test_one_email_cannot_hold_two_roles(client):
    """Register a parent, then try to re-register the same email as a student.

    One email is one role: the second attempt is refused, not converted.
    """
    r = client.post("/api/v1/auth/parent/register", json={
        "email": "dual@example.com", "password": "hunter2!",
        "student_email": "kid@example.com",
    })
    assert r.status_code == 201

    r = client.post("/api/v1/auth/signup", json={
        "email": "dual@example.com", "password": "hunter2!",
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Email already registered"


def test_parent_email_cannot_be_reused_for_a_student_account(client, parent):
    r = client.post("/api/v1/auth/signup", json={
        "email": parent.email, "password": "hunter2!",
    })
    assert r.status_code == 400