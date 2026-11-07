"""Admin dashboard: role enforcement, pagination, and existing-data views."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.enums import LinkStatus, UserRole
from app.models.user import ParentStudentLink, User
from tests.conftest import auth_header


@pytest.fixture()
def admin(db):
    user = User(
        email="admin@example.com",
        password_hash="not-a-real-hash",
        role=UserRole.ADMIN,
        first_name="Ada",
        last_name="Admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _student(db, email, **kwargs):
    user = User(
        email=email,
        password_hash="not-a-real-hash",
        first_name=kwargs.pop("first_name", "Paged"),
        last_name=kwargs.pop("last_name", "Student"),
        **kwargs,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_admin_routes_require_authentication(client):
    assert client.get("/api/v1/admin/dashboard").status_code == 401
    assert client.get("/api/v1/admin/students").status_code == 401
    assert client.get("/api/v1/admin/students/1").status_code == 401
    assert client.patch("/api/v1/admin/students/1/status", json={"is_active": False}).status_code == 401
    assert client.get("/api/v1/admin/parents").status_code == 401
    assert client.get("/api/v1/admin/parents/1").status_code == 401
    assert client.get("/api/v1/admin/ai-mentors").status_code == 401
    assert client.post("/api/v1/admin/ai-mentors/1/retry").status_code == 401


@pytest.mark.parametrize("fixture_name,role", [("user", "student"), ("parent", "parent")])
def test_non_admin_roles_are_forbidden(client, request, fixture_name, role):
    caller = request.getfixturevalue(fixture_name)
    headers = auth_header(caller.id, role)
    for path in ("/api/v1/admin/dashboard", "/api/v1/admin/students", "/api/v1/admin/parents"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, path


@pytest.mark.parametrize("expected_role", ["parent", "student"])
def test_admin_can_log_in_from_either_public_login_tab(client, db, admin, expected_role):
    admin.password_hash = hash_password("Admin-test-pass")
    db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "Admin-test-pass", "expected_role": expected_role},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_dashboard_counts_existing_users_and_agent_status(client, db, admin, user, parent, active_link):
    inactive = _student(db, "inactive@example.com", is_active=False)
    active_agent = _student(db, "active-agent@example.com", ai_agent_status="active")
    active_agent.letta_agent_id = "agent-active"
    legacy_agent = _student(db, "legacy-agent@example.com", letta_agent_id="agent-legacy")
    failed_agent = _student(db, "failed-agent@example.com", ai_agent_status="failed", ai_agent_attempts=3)
    db.commit()

    body = client.get("/api/v1/admin/dashboard", headers=auth_header(admin.id, "admin")).json()
    assert body["total_students"] == 5  # user + inactive + active + legacy + failed
    assert body["total_parents"] == 1
    assert body["active_students"] == 4
    assert body["active_ai_mentors"] == 2  # active status + legacy id fallback
    assert body["new_registrations_7d"] == db.scalar(select(func.count(User.id)))
    assert failed_agent.is_active is True and inactive.is_active is False


def test_student_list_is_paginated_searchable_and_marks_parent_links(
    client, db, admin, user, parent, active_link
):
    for index in range(5):
        _student(db, f"paged{index}@example.com", first_name=f"Paged {index}")

    headers = auth_header(admin.id, "admin")
    page = client.get(
        "/api/v1/admin/students?search=Paged&page=2&page_size=2", headers=headers
    ).json()
    assert page["total"] == 5
    assert page["pages"] == 3
    assert page["page"] == 2
    assert len(page["items"]) == 2
    assert all(item["has_linked_parent"] is False for item in page["items"])

    linked = client.get(
        f"/api/v1/admin/students?search={user.email}", headers=headers
    ).json()
    assert linked["total"] == 1
    assert linked["items"][0]["has_linked_parent"] is True
    assert set(linked["items"][0]) == {
        "id", "name", "email", "grade", "school", "is_active", "created_at", "has_linked_parent",
    }

    empty = client.get("/api/v1/admin/students?search=nobody", headers=headers).json()
    assert empty["total"] == 0 and empty["items"] == []


def test_student_detail_and_status_toggle(client, db, admin, user, parent, active_link):
    headers = auth_header(admin.id, "admin")
    detail = client.get(f"/api/v1/admin/students/{user.id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["email"] == user.email
    assert body["linked_parents"] == [
        {
            "id": parent.id,
            "name": parent.display_name,
            "email": parent.email,
            "status": LinkStatus.ACTIVE.value,
            "linked_at": active_link.created_at.isoformat(),
        }
    ]

    disabled = client.patch(
        f"/api/v1/admin/students/{user.id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert disabled.status_code == 200 and disabled.json()["is_active"] is False
    db.refresh(user)
    assert user.is_active is False

    enabled = client.patch(
        f"/api/v1/admin/students/{user.id}/status",
        json={"is_active": True},
        headers=headers,
    )
    assert enabled.status_code == 200 and enabled.json()["is_active"] is True

    assert client.get("/api/v1/admin/students/999999", headers=headers).status_code == 404
    assert client.patch(
        "/api/v1/admin/students/999999/status",
        json={"is_active": False},
        headers=headers,
    ).status_code == 404


def test_parent_list_and_detail_show_linked_children(client, db, admin, user, parent, active_link):
    headers = auth_header(admin.id, "admin")
    listing = client.get("/api/v1/admin/parents", headers=headers).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == parent.id
    assert listing["items"][0]["linked_children_count"] == 1
    assert set(listing["items"][0]) == {
        "id", "name", "email", "is_active", "created_at", "linked_children_count",
    }

    detail = client.get(f"/api/v1/admin/parents/{parent.id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["linked_children"][0]["id"] == user.id
    assert body["linked_children"][0]["status"] == LinkStatus.ACTIVE.value
    assert client.get("/api/v1/admin/parents/999999", headers=headers).status_code == 404


def test_ai_mentors_lists_every_student_with_derived_status(client, db, admin, user):
    active = _student(db, "mentor-active@example.com", ai_agent_status="active", letta_agent_id="agent-1")
    failed = _student(db, "mentor-failed@example.com", ai_agent_status="failed", ai_agent_attempts=2)
    legacy = _student(db, "mentor-legacy@example.com", letta_agent_id="agent-legacy")

    body = client.get(
        "/api/v1/admin/ai-mentors?page_size=100", headers=auth_header(admin.id, "admin")
    ).json()
    assert body["total"] == 4
    by_id = {item["student_id"]: item for item in body["items"]}
    assert by_id[user.id]["status"] == "not_created"
    assert by_id[user.id]["agent_id"] is None
    assert by_id[active.id]["status"] == "active"
    assert by_id[failed.id]["status"] == "failed"
    assert by_id[failed.id]["attempts"] == 2
    assert by_id[legacy.id]["status"] == "active"


def test_retry_only_for_failed_agents_and_increments_attempts(client, db, admin):
    failed = _student(
        db,
        "retry-failed@example.com",
        ai_agent_status="failed",
        ai_agent_attempts=1,
    )
    healthy = _student(db, "retry-healthy@example.com", ai_agent_status="active")
    headers = auth_header(admin.id, "admin")

    response = client.post(f"/api/v1/admin/ai-mentors/{failed.id}/retry", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["attempts"] == 2
    assert body["status"] == "failed"  # Letta is disabled in tests.

    assert client.post(
        f"/api/v1/admin/ai-mentors/{healthy.id}/retry", headers=headers
    ).status_code == 400
    assert client.post("/api/v1/admin/ai-mentors/999999/retry", headers=headers).status_code == 404


def test_admin_dashboard_relative_time_filter(client, db, admin):
    old = _student(db, "old-registration@example.com")
    old.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db.commit()

    body = client.get("/api/v1/admin/dashboard", headers=auth_header(admin.id, "admin")).json()
    assert body["new_registrations_7d"] == 1
