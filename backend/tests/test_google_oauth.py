import os
import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")
os.environ.setdefault("LETTA_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-oauth-tests")

# ---------------------------------------------------------------------------
# Unit tests: state build / verify (no HTTP, no settings needed)
# ---------------------------------------------------------------------------
class TestStateRoundTrip:
    def test_roundtrip_student(self):
        from app.services.auth import build_oauth_state, verify_oauth_state
        state = build_oauth_state("mynonce", "/login", "student")
        assert verify_oauth_state(state) == ("mynonce", "student", "/login")

    def test_roundtrip_parent(self):
        from app.services.auth import build_oauth_state, verify_oauth_state
        state = build_oauth_state("abc", "/signup", "parent")
        nonce, intent, path = verify_oauth_state(state)
        assert (nonce, intent, path) == ("abc", "parent", "/signup")

    def test_tampered_sig_rejected(self):
        from app.services.auth import build_oauth_state, verify_oauth_state
        state = build_oauth_state("nonce", "/login", "student")
        tampered = state[:-1] + ("x" if state[-1] != "x" else "y")
        assert verify_oauth_state(tampered) is None

    def test_tampered_payload_rejected(self):
        from app.services.auth import build_oauth_state, verify_oauth_state
        state = build_oauth_state("nonce", "/login", "student")
        tampered = state.replace(":student:", ":parent:", 1)
        assert verify_oauth_state(tampered) is None

    def test_empty_state_rejected(self):
        from app.services.auth import verify_oauth_state
        assert verify_oauth_state("") is None
        assert verify_oauth_state("nopayload") is None


# ---------------------------------------------------------------------------
# Fixtures: patch settings so integration tests see Google vars + FRONTEND_URL
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def patch_settings():
    """Patch the cached settings singleton for every test in this module."""
    from app.core.config import settings
    orig_client_id = settings.GOOGLE_CLIENT_ID
    orig_secret = settings.GOOGLE_CLIENT_SECRET
    orig_redirect = settings.GOOGLE_REDIRECT_URI
    orig_frontend = settings.FRONTEND_URL
    settings.GOOGLE_CLIENT_ID = "test-client-id"
    settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
    settings.GOOGLE_REDIRECT_URI = "https://novi-tech.onrender.com/api/auth/google/callback"
    settings.FRONTEND_URL = "https://novi-tech.vercel.app"
    yield
    settings.GOOGLE_CLIENT_ID = orig_client_id
    settings.GOOGLE_CLIENT_SECRET = orig_secret
    settings.GOOGLE_REDIRECT_URI = orig_redirect
    settings.FRONTEND_URL = orig_frontend


@pytest.fixture()
def oauth_client(db):
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.main import app
    def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _make_state(nonce, next_path="/login", intent="student"):
    from app.services.auth import build_oauth_state
    return build_oauth_state(nonce, next_path, intent)


# ---------------------------------------------------------------------------
# OAuth initiation tests
# ---------------------------------------------------------------------------
class TestOAuthStart:
    def test_redirects_to_google(self, oauth_client):
        resp = oauth_client.get("/api/auth/google", follow_redirects=False)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "accounts.google.com" in loc
        assert "client_id=test-client-id" in loc
        assert "response_type=code" in loc

    def test_sets_csrf_cookie(self, oauth_client):
        resp = oauth_client.get("/api/auth/google", follow_redirects=False)
        assert "google_oauth_state" in resp.cookies

    def test_invalid_next_clamped(self, oauth_client):
        resp = oauth_client.get("/api/auth/google?next=//evil.com", follow_redirects=False)
        assert resp.status_code == 302
        assert "accounts.google.com" in resp.headers["location"]

    def test_invalid_intent_defaults_to_student(self, oauth_client):
        resp = oauth_client.get("/api/auth/google?intent=admin", follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Callback: missing code / state
# ---------------------------------------------------------------------------
class TestOAuthCallbackMissingCode:
    def test_no_params_redirects_with_requires_code(self, oauth_client):
        resp = oauth_client.get("/api/auth/google/callback", follow_redirects=False)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "google_error=google_oauth_requires_code" in loc
        assert "novi-tech.vercel.app/login" in loc

    def test_code_without_state_redirects_with_error(self, oauth_client):
        resp = oauth_client.get("/api/auth/google/callback?code=xyz", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_requires_code" in resp.headers["location"]

    def test_google_error_param_returns_cancelled(self, oauth_client):
        """Google returns ?error=access_denied — must not become requires_code."""
        resp = oauth_client.get(
            "/api/auth/google/callback?error=access_denied",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        # Should be cancelled, not requires_code
        assert "google_oauth_cancelled" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Callback: CSRF guard
# ---------------------------------------------------------------------------
class TestOAuthCallbackCSRF:
    def test_missing_cookie_returns_expired(self, oauth_client):
        nonce = "nonce123"
        state = _make_state(nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=x&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_expired" in resp.headers["location"]

    def test_cookie_mismatch_returns_verification_failed(self, oauth_client):
        nonce = "real-nonce"
        state = _make_state(nonce)
        oauth_client.cookies.set("google_oauth_state", "wrong-nonce")
        resp = oauth_client.get(f"/api/auth/google/callback?code=x&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_verification_failed" in resp.headers["location"]

    def test_tampered_state_returns_verification_failed(self, oauth_client):
        nonce = "real-nonce"
        state = _make_state(nonce)
        tampered = state[:-1] + ("x" if state[-1] != "x" else "y")
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=x&state={tampered}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_verification_failed" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Callback: happy path
# ---------------------------------------------------------------------------
def _patch_google_helpers(monkeypatch, email="student@example.com",
                          name="Test Student", verified="true"):
    from app.services import auth as auth_svc
    from app.core.config import settings

    async def fake_exchange(code):
        return {"id_token": "fake-id-token"}

    async def fake_verify(id_token):
        return {
            "email": email,
            "email_verified": verified,
            "name": name,
            "aud": settings.GOOGLE_CLIENT_ID,
        }

    monkeypatch.setattr(auth_svc, "_exchange_google_code", fake_exchange)
    monkeypatch.setattr(auth_svc, "_verify_google_id_token", fake_verify)


class TestOAuthCallbackHappyPath:
    def test_new_student_redirected_to_vercel(self, oauth_client, db, monkeypatch):
        _patch_google_helpers(monkeypatch)
        nonce = "happy-student"
        state = _make_state(nonce, "/login", "student")
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=good&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        loc = resp.headers["location"]
        assert "novi-tech.vercel.app" in loc
        assert "google_token=" in loc
        assert "google_error" not in loc
        assert "google_new=1" in loc

    def test_existing_student_is_google_new_0(self, oauth_client, db, monkeypatch):
        from app.models.user import User
        from app.core import security
        existing = User(email="existing@example.com",
                        password_hash=security.hash_password("pw"),
                        first_name="Exists", last_name="Already", grade=10)
        db.add(existing); db.commit(); db.refresh(existing)
        _patch_google_helpers(monkeypatch, email="existing@example.com", name="Exists Already")
        nonce = "existing-nonce"
        state = _make_state(nonce)
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=good&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_new=0" in resp.headers["location"]

    def test_new_parent_gets_parent_role(self, oauth_client, db, monkeypatch):
        _patch_google_helpers(monkeypatch, email="newparent@example.com", name="Pat Parent")
        nonce = "parent-nonce"
        state = _make_state(nonce, "/signup", "parent")
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=good&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_token=" in resp.headers["location"]
        from sqlalchemy import select
        from app.models.user import User, UserRole
        user = db.scalar(select(User).where(User.email == "newparent@example.com"))
        assert user is not None
        assert user.role == UserRole.PARENT

    def test_unverified_email_rejected(self, oauth_client, db, monkeypatch):
        _patch_google_helpers(monkeypatch, email="unverified@example.com", verified="false")
        nonce = "unverified-nonce"
        state = _make_state(nonce)
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=good&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_rejected" in resp.headers["location"]

    def test_csrf_cookie_cleared_on_success(self, oauth_client, db, monkeypatch):
        _patch_google_helpers(monkeypatch, email="cookieclear@example.com")
        nonce = "cookie-clear"
        state = _make_state(nonce)
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=good&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_state" in resp.headers.get("set-cookie", "")

    def test_token_exchange_failure_redirects_to_failed(self, oauth_client, db, monkeypatch):
        from app.services import auth as auth_svc
        async def bad_exchange(code):
            raise Exception("token exchange failed")
        monkeypatch.setattr(auth_svc, "_exchange_google_code", bad_exchange)
        nonce = "fail-nonce"
        state = _make_state(nonce)
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=bad&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_oauth_failed" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Role preservation
# ---------------------------------------------------------------------------
class TestRolePreservation:
    def test_existing_student_not_promoted_to_parent(self, oauth_client, db, monkeypatch):
        from app.models.user import User, UserRole
        from app.core import security
        student = User(email="notaparent@example.com",
                       password_hash=security.hash_password("pw"),
                       first_name="Still", last_name="Student", grade=11)
        db.add(student); db.commit(); db.refresh(student)
        _patch_google_helpers(monkeypatch, email="notaparent@example.com", name="Still Student")
        nonce = "role-guard"
        state = _make_state(nonce, "/signup", "parent")
        oauth_client.cookies.set("google_oauth_state", nonce)
        resp = oauth_client.get(f"/api/auth/google/callback?code=x&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        assert "google_token=" in resp.headers["location"]
        from sqlalchemy import select
        user = db.scalar(select(User).where(User.email == "notaparent@example.com"))
        assert user.role == UserRole.STUDENT
