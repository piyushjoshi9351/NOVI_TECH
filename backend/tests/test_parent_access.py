"""IDOR + scope enforcement on the parent-facing HTTP surface.

The threat model: an authenticated parent who knows or guesses another family's
``student_id`` (or another student's link id) tries to read that student's data.
Every test below should end in a 404/403 and reveal nothing.
"""

import pytest

from app.core.deps import require_scope
from app.services import parent_links
from tests.conftest import auth_header


def _approve(db, parent, student):
    link = parent_links.create_pending_link(db, parent, student.email)
    return parent_links.approve_link(db, link)


# ------------------------------------------------------------------ router-level 404
def test_parent_cannot_read_unlinked_student(client, db, parent, other_student):
    other_student.id  # ensure id exists
    r = client.get(
        f"/api/v1/parent/students/{other_student.id}/overview",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 404


def test_guessing_another_students_id_looks_identical_to_a_missing_one(client, parent, other_student):
    """404 for 'exists but not yours' and 404 for 'does not exist' must match."""
    r_real = client.get(
        f"/api/v1/parent/students/{other_student.id}/overview",
        headers=auth_header(parent.id, "parent"),
    )
    r_fake = client.get(
        "/api/v1/parent/students/999999/overview",
        headers=auth_header(parent.id, "parent"),
    )
    assert r_real.status_code == r_fake.status_code == 404
    assert r_real.json()["detail"] == r_fake.json()["detail"]


def test_pending_link_grants_no_access(client, db, parent, user, pending_link):
    assert pending_link.status.value == "pending"
    r = client.get(
        f"/api/v1/parent/students/{user.id}/overview",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 404


def test_revoked_link_loses_access_immediately(client, db, parent, user, active_link):
    parent_links.revoke_link(db, active_link)
    r = client.get(
        f"/api/v1/parent/students/{user.id}/overview",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 404


def test_other_parent_cannot_use_a_shared_student_id(client, db, parent, other_parent, user, active_link):
    """The link is scoped to the parent, not just the student."""
    r = client.get(
        f"/api/v1/parent/students/{user.id}/overview",
        headers=auth_header(other_parent.id, "parent"),
    )
    assert r.status_code == 404


def test_students_are_rejected_from_parent_endpoints(client, user):
    r = client.get(
        f"/api/v1/parent/students/{user.id}/overview",
        headers=auth_header(user.id, "student"),
    )
    assert r.status_code == 403


def test_parent_is_rejected_from_student_endpoints(client, parent, active_link):
    r = client.get("/api/v1/student/parent-links", headers=auth_header(parent.id, "parent"))
    assert r.status_code == 403


def test_unauthenticated_is_401(client, user, active_link):
    assert client.get("/api/v1/parent/students").status_code == 401
    assert client.get("/api/v1/student/parent-links").status_code == 401


# ------------------------------------------------------------------ scopes
def test_basic_scope_gets_an_empty_insights_section(client, parent, user, active_link):
    """Unshared is NOT an error: 200 with an empty section.

    A 403 here would make the whole dashboard look broken to a parent who simply
    has basic consent, which is the common case.
    """
    r = client.get(
        f"/api/v1/parent/students/{user.id}/insights",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["basic"]
    assert body["top_interests"] == []
    assert body["focus_areas"] == []
    assert body["novi_insight"] is None


def test_basic_scope_gets_a_null_growth_section(client, parent, user, active_link):
    r = client.get(
        f"/api/v1/parent/students/{user.id}/memory",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scopes"] == ["basic"]
    assert body["growth"] is None


def test_overview_is_allowed_with_basic_scope(client, parent, user, active_link):
    r = client.get(
        f"/api/v1/parent/students/{user.id}/overview",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200


def test_granting_insights_unlocks_only_insights(client, db, parent, user, active_link):
    parent_links.set_scopes(db, active_link, {"insights": True, "memory": False})
    h = auth_header(parent.id, "parent")

    insights = client.get(f"/api/v1/parent/students/{user.id}/insights", headers=h)
    assert insights.status_code == 200
    assert "insights" in insights.json()["scopes"]

    growth = client.get(f"/api/v1/parent/students/{user.id}/memory", headers=h)
    assert growth.status_code == 200
    assert growth.json()["growth"] is None


def test_revoking_scopes_takes_effect_immediately(client, db, parent, user, active_link):
    parent_links.set_scopes(db, active_link, {"insights": True, "memory": False})
    h = auth_header(parent.id, "parent")
    assert "insights" in client.get(
        f"/api/v1/parent/students/{user.id}/insights", headers=h
    ).json()["scopes"]

    parent_links.set_scopes(db, active_link, {"insights": False, "memory": False})
    body = client.get(f"/api/v1/parent/students/{user.id}/insights", headers=h).json()
    assert body["scopes"] == ["basic"]
    assert body["top_interests"] == []


def test_scope_check_runs_before_the_handler(client, parent, other_student):
    """A missing link must 404 even on a scope-gated route."""
    r = client.get(
        f"/api/v1/parent/students/{other_student.id}/insights",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 404


def test_require_scope_rejects_unknown_scope_at_build_time():
    with pytest.raises(ValueError):
        require_scope("secrets")


def test_require_scope_builds_for_known_scopes():
    for name in ("basic", "insights", "memory"):
        assert callable(require_scope(name))


# ------------------------------------------------------------------ student side
def test_student_cannot_touch_another_students_link(client, db, other_student, pending_link):
    """Link ids from another student must be indistinguishable from missing."""
    h = auth_header(other_student.id, "student")
    assert client.post(f"/api/v1/student/parent-links/{pending_link.id}/approve", headers=h).status_code == 404
    assert client.post(f"/api/v1/student/parent-links/{pending_link.id}/revoke", headers=h).status_code == 404
    assert client.patch(
        f"/api/v1/student/parent-links/{pending_link.id}/scopes",
        json={"insights": True},
        headers=h,
    ).status_code == 404


def test_student_approves_then_parent_can_read(client, db, parent, user, pending_link):
    h_student = auth_header(user.id, "student")
    h_parent = auth_header(parent.id, "parent")

    assert client.get(
        f"/api/v1/parent/students/{user.id}/overview", headers=h_parent
    ).status_code == 404

    r = client.post(f"/api/v1/student/parent-links/{pending_link.id}/approve", headers=h_student)
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    assert client.get(
        f"/api/v1/parent/students/{user.id}/overview", headers=h_parent
    ).status_code == 200


def test_student_revoke_then_parent_loses_access(client, db, parent, user, active_link):
    h_student = auth_header(user.id, "student")
    h_parent = auth_header(parent.id, "parent")

    assert client.get(f"/api/v1/parent/students/{user.id}/overview", headers=h_parent).status_code == 200
    r = client.post(f"/api/v1/student/parent-links/{active_link.id}/revoke", headers=h_student)
    assert r.status_code == 200
    assert client.get(f"/api/v1/parent/students/{user.id}/overview", headers=h_parent).status_code == 404


def test_student_updates_scopes(client, db, user, active_link):
    h = auth_header(user.id, "student")
    r = client.patch(
        f"/api/v1/student/parent-links/{active_link.id}/scopes",
        json={"insights": True, "memory": True},
        headers=h,
    )
    assert r.status_code == 200
    assert set(r.json()["scopes"]) == {"basic", "insights", "memory"}


def test_student_cannot_remove_basic_scope(client, user, active_link):
    r = client.patch(
        f"/api/v1/student/parent-links/{active_link.id}/scopes",
        json={"insights": False, "memory": False},
        headers=auth_header(user.id, "student"),
    )
    assert "basic" in r.json()["scopes"]


def test_student_link_list_omits_revoked(client, db, user, active_link):
    h = auth_header(user.id, "student")
    client.post(f"/api/v1/student/parent-links/{active_link.id}/revoke", headers=h)
    assert client.get("/api/v1/student/parent-links", headers=h).json()["links"] == []


# ------------------------------------------------------------------ parent links API
def test_parent_link_request_returns_generic_message(client, parent, user):
    r = client.post(
        "/api/v1/parent/links",
        json={"student_email": user.email},
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert "sent them a request" in r.json()["message"]


def test_parent_link_request_is_identical_for_unknown_email(client, parent, user):
    """The response must not reveal whether the email is registered."""
    known = client.post(
        "/api/v1/parent/links",
        json={"student_email": user.email},
        headers=auth_header(parent.id, "parent"),
    ).json()
    unknown = client.post(
        "/api/v1/parent/links",
        json={"student_email": "nobody@nowhere.test"},
        headers=auth_header(parent.id, "parent"),
    ).json()
    assert known["message"] == unknown["message"]
    assert known["status"] == unknown["status"]


def test_parent_student_list_hides_pending_student_details(client, parent, user, pending_link):
    r = client.get("/api/v1/parent/students", headers=auth_header(parent.id, "parent"))
    assert r.status_code == 200
    link = r.json()["links"][0]
    assert link["status"] == "pending"
    assert link["student"] is None


def test_parent_student_list_shows_active_student(client, parent, user, active_link):
    r = client.get("/api/v1/parent/students", headers=auth_header(parent.id, "parent"))
    link = r.json()["links"][0]
    assert link["status"] == "active"
    assert link["student"]["first_name"] == "Test"
    assert link["student"]["grade"] == 10


def test_parent_student_list_never_echoes_full_invited_email(client, parent, pending_link):
    r = client.get("/api/v1/parent/students", headers=auth_header(parent.id, "parent"))
    assert "student@example.com" not in r.text


def test_parent_cannot_create_links_as_a_student(client, user):
    r = client.post(
        "/api/v1/parent/links",
        json={"student_email": "x@y.test"},
        headers=auth_header(user.id, "student"),
    )
    assert r.status_code == 403