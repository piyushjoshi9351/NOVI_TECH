"""Local-password provenance and safe parent-facing account lifecycle labels."""

from datetime import datetime, timezone
import re
import sqlite3

from app.core.security import hash_password
from app.db.run_migrations import CRITICAL_COLUMNS, MIGRATIONS_DIR, _statements
from app.models.enums import LinkStatus
from app.schemas.parent import ParentStudentCreate
from app.services import auth as auth_service
from app.services.parent_students import create_student
from tests.conftest import auth_header

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
CHANGE = "/api/v1/auth/change-password"


def test_new_password_accounts_report_local_password(client, parent):
    response = client.post("/api/v1/auth/parent/register", json={"name": "Parent", "email": "fresh@example.com", "password": "Parent-password"})
    assert response.status_code == 201
    assert response.json()["user"]["has_local_password"] is True
    assert client.get(ME, headers=auth_header(parent.id, "parent")).json()["has_local_password"] is True


def test_google_only_account_reports_flag_and_rejects_local_password_changes(client, db):
    google, _ = auth_service._upsert_google_user("google@example.com", "Google Parent", None, db, "parent")
    assert google.has_local_password is False and google.first_login_at is not None
    # Even an accidentally known hash must not enable Google-only password auth.
    google.password_hash = hash_password("Known-but-disabled")
    db.commit()
    headers = auth_header(google.id, "parent")
    assert client.get(ME, headers=headers).json()["has_local_password"] is False
    assert client.post(LOGIN, json={"email": google.email, "password": "Known-but-disabled"}).status_code == 401
    assert client.post(CHANGE, json={"current_password": "Known-but-disabled", "new_password": "Replacement-password"}, headers=headers).status_code == 400
    db.refresh(google)
    assert google.has_local_password is False and google.token_version == 0


def test_unknown_legacy_provenance_is_confirmed_only_by_successful_password_login(client, db, user):
    user.has_local_password = None
    user.password_hash = hash_password("Legacy-password")
    db.commit()
    assert client.get(ME, headers=auth_header(user.id)).json()["has_local_password"] is None
    assert client.post(LOGIN, json={"email": user.email, "password": "Wrong-password"}).status_code == 401
    db.refresh(user)
    assert user.has_local_password is None and user.first_login_at is None
    # Google cannot tell us whether an unrelated local credential was usable.
    auth_service._upsert_google_user(user.email, "Ignored", None, db)
    assert user.has_local_password is None
    response = client.post(LOGIN, json={"email": user.email, "password": "Legacy-password"})
    assert response.status_code == 200 and response.json()["user"]["has_local_password"] is True


def test_google_login_preserves_an_existing_usable_local_password(db, user):
    original_hash = user.password_hash
    auth_service._upsert_google_user(user.email, "Ignored", None, db)
    assert user.has_local_password is True and user.password_hash == original_hash


def test_parent_lifecycle_tracks_real_sign_in_password_setup_and_onboarding(client, db, parent):
    receipt = create_student(db, parent, ParentStudentCreate(name="Child", email="child-state@example.com", password="Temporary-password"))
    parent_headers = auth_header(parent.id, "parent")

    def state():
        response = client.get("/api/v1/parent/students", headers=parent_headers)
        assert response.status_code == 200
        row = next(link for link in response.json()["links"] if link["id"] == receipt.link_id)
        assert "first_login_at" not in row and "has_local_password" not in row
        assert set(row["student"]) == {"first_name", "grade"}
        return row["account_state"]

    assert state() == "awaiting_first_login"
    login = client.post(LOGIN, json={"email": "child-state@example.com", "password": "Temporary-password"})
    assert login.status_code == 200 and login.json()["user"]["has_local_password"] is True
    assert state() == "onboarding_in_progress"
    changed = client.post(CHANGE, json={"current_password": "Temporary-password", "new_password": "Independent-password"}, headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert changed.status_code == 200 and changed.json()["user"]["has_local_password"] is True
    assert state() == "onboarding_in_progress"
    from app.models.user import User
    child = db.get(User, receipt.student_id)
    first_login_at = child.first_login_at
    child.onboarding_completed_at = datetime.now(timezone.utc)
    db.commit()
    assert state() == "active"
    client.post(LOGIN, json={"email": child.email, "password": "Independent-password"})
    db.refresh(child)
    assert child.first_login_at == first_login_at


def test_nonactive_legacy_rows_do_not_expose_account_state(client, parent, pending_link):
    row = client.get("/api/v1/parent/students", headers=auth_header(parent.id, "parent")).json()["links"][0]
    assert row["account_state"] is None and row["student"] is None


def test_student_relationship_metadata_separates_parent_creation_and_legacy_review(client, db, user, active_link, other_parent):
    from app.models.user import ParentStudentLink
    active_link.activation_source = "parent_created"
    legacy = ParentStudentLink(parent_id=other_parent.id, student_id=user.id, status=LinkStatus.PENDING)
    db.add(legacy)
    db.commit()
    rows = {row["id"]: row for row in client.get("/api/v1/student/parent-links", headers=auth_header(user.id)).json()["links"]}
    assert rows[active_link.id]["activation_source"] == "parent_created"
    assert rows[active_link.id]["can_manage"] is True and rows[active_link.id]["can_approve"] is False
    assert rows[legacy.id]["can_approve"] is True


def test_metadata_migration_leaves_legacy_history_unknown_and_preserves_hashes():
    statements = _statements(MIGRATIONS_DIR / "0009_account_sign_in_metadata.sql")
    ddl = [match for statement in statements for match in re.findall(r"'(ALTER TABLE `users` ADD COLUMN [^']+)'", statement)]
    assert len(ddl) == 2
    assert not any(statement.upper().startswith(("UPDATE", "DELETE", "INSERT")) for statement in statements)
    assert ("users", "has_local_password") in CRITICAL_COLUMNS
    assert ("users", "first_login_at") in CRITICAL_COLUMNS
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, password_hash TEXT)")
        db.executemany("INSERT INTO users VALUES (?, ?)", [(1, "legacy-password-hash"), (2, "legacy-google-random-hash")])
        for statement in ddl:
            db.execute(statement)
        assert db.execute("SELECT password_hash, has_local_password, first_login_at FROM users ORDER BY id").fetchall() == [("legacy-password-hash", None, None), ("legacy-google-random-hash", None, None)]
