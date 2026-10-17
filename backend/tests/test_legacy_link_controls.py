"""Retired request APIs, legacy consent transitions, and per-parent scopes."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.enums import LinkStatus
from app.models.career_dna import CareerDNA
from app.models.user import ParentStudentLink
from app.services import parent_links, parents
from tests.conftest import auth_header


@pytest.mark.parametrize("path", ["/api/v1/parent/links", "/api/v1/parents/link"])
def test_retired_requests_never_mutate_links_or_send_invites(client, db, parent, user, pending_link, monkeypatch, path):
    sender = Mock()
    monkeypatch.setattr(parent_links, "get_invite_sender", sender)
    before = (pending_link.status, dict(pending_link.scopes), pending_link.student_id, pending_link.expires_at)
    for body in ({"student_email": user.email}, {"student_email": "unknown@example.com"}, {}):
        response = client.post(path, json=body, headers=auth_header(parent.id, "parent"))
        assert response.status_code == 410
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 1
    db.refresh(pending_link)
    assert (pending_link.status, pending_link.scopes, pending_link.student_id, pending_link.expires_at) == before
    sender.assert_not_called()
    assert client.post(path).status_code == 401
    assert client.post(path, headers=auth_header(user.id)).status_code == 403


def test_retired_legacy_service_cannot_create_pending_requests(db, parent, user):
    with pytest.raises(HTTPException) as exc:
        parents.request_link(db, parent, user.email)
    assert exc.value.status_code == 410
    assert db.scalar(select(func.count()).select_from(ParentStudentLink)) == 0


@pytest.mark.parametrize("state", [LinkStatus.ACTIVE, LinkStatus.REVOKED])
def test_approval_accepts_only_pending_and_preserves_nonpending_links(client, db, parent, user, active_link, state):
    if state == LinkStatus.REVOKED:
        parent_links.revoke_link(db, active_link)
    before = (active_link.status, active_link.confirmed_at, active_link.revoked_at, dict(active_link.scopes))
    response = client.post(f"/api/v1/student/parent-links/{active_link.id}/approve", headers=auth_header(user.id))
    assert response.status_code == 409
    db.refresh(active_link)
    assert (active_link.status, active_link.confirmed_at, active_link.revoked_at, active_link.scopes) == before
    expected = 200 if state == LinkStatus.ACTIVE else 404
    assert client.get(f"/api/v1/parent/students/{user.id}/overview", headers=auth_header(parent.id, "parent")).status_code == expected


def test_approval_reloads_state_before_deciding(db, pending_link):
    # Simulate a revoke committed since the service caller loaded its object.
    db.execute(ParentStudentLink.__table__.update().where(ParentStudentLink.id == pending_link.id).values(status=LinkStatus.REVOKED))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        parent_links.approve_link(db, pending_link)
    assert exc.value.status_code == 409
    assert db.get(ParentStudentLink, pending_link.id).status == LinkStatus.REVOKED


@pytest.mark.parametrize("attached", [False, True])
def test_expired_invitation_cannot_be_approved(db, parent, user, attached):
    link = ParentStudentLink(parent_id=parent.id, student_id=user.id if attached else None, invited_email=user.email, status=LinkStatus.PENDING, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    db.add(link)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        parent_links.approve_link(db, link)
    assert exc.value.status_code == 410
    db.refresh(link)
    assert link.status == LinkStatus.PENDING and link.confirmed_at is None
    assert link.activated_at is None and link.activation_source is None


def test_expired_pending_link_http_approval_returns_gone(client, db, user, pending_link):
    pending_link.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    response = client.post(f"/api/v1/student/parent-links/{pending_link.id}/approve", headers=auth_header(user.id))
    assert response.status_code == 410
    assert pending_link.status == LinkStatus.PENDING


def test_successful_legacy_approval_records_student_consent_without_changing_scopes(db, pending_link):
    pending_link.scopes = {"basic": True, "insights": False, "memory": True}
    pending_link.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    db.commit()
    parent_links.approve_link(db, pending_link)
    assert pending_link.status == LinkStatus.ACTIVE
    assert pending_link.activation_source == "student_approved"
    assert pending_link.activated_at == pending_link.confirmed_at
    assert pending_link.confirmed_at is not None
    assert pending_link.scopes == {"basic": True, "insights": False, "memory": True}


@pytest.mark.parametrize("state,expired,resolves", [
    (LinkStatus.PENDING, True, False), (LinkStatus.REVOKED, False, False),
    (LinkStatus.ACTIVE, False, False), (LinkStatus.PENDING, False, True),
])
def test_legacy_resolution_respects_status_expiry_and_never_activates(db, parent, user, state, expired, resolves):
    link = ParentStudentLink(parent_id=parent.id, invited_email=user.email, status=state, scopes={"basic": True, "memory": True}, expires_at=datetime.now(timezone.utc) + timedelta(days=-1 if expired else 1))
    db.add(link)
    db.commit()
    result = parent_links.resolve_invitations_for_student(db, user)
    assert bool(result) == resolves
    db.refresh(link)
    assert link.student_id == (user.id if resolves else None)
    assert link.status == state and link.scopes == {"basic": True, "memory": True}
    assert link.confirmed_at is None and link.activation_source is None


@pytest.mark.parametrize("full_parent_first", [True, False])
def test_legacy_dashboard_uses_requesting_parents_scopes(client, db, parent, other_parent, user, monkeypatch, full_parent_first):
    full = ParentStudentLink(parent_id=parent.id, student_id=user.id, status=LinkStatus.ACTIVE, scopes={"basic": True, "insights": True})
    basic = ParentStudentLink(parent_id=other_parent.id, student_id=user.id, status=LinkStatus.ACTIVE, scopes={"basic": True})
    db.add_all([full, basic] if full_parent_first else [basic, full])
    db.commit()

    def snapshot(db, child, link):
        data = {"first_name": child.first_name, "basic": {"profile_strength": 35}}
        if link.has_scope("insights"):
            data["insights"] = {"focus_areas": ["Shared only with the full parent"]}
        return data

    monkeypatch.setattr(parents.projection, "consented_snapshot", snapshot)
    full_result = client.get("/api/v1/parents/dashboard", headers=auth_header(parent.id, "parent"))
    basic_result = client.get("/api/v1/parents/dashboard", headers=auth_header(other_parent.id, "parent"))
    assert full_result.status_code == basic_result.status_code == 200
    assert full_result.json()["children"][0]["month_focus"] == ["Shared only with the full parent"]
    assert basic_result.json()["children"][0]["month_focus"] == []
    assert "Shared only with the full parent" not in basic_result.text
    parent_links.revoke_link(db, basic)
    assert client.get("/api/v1/parents/dashboard", headers=auth_header(other_parent.id, "parent")).json()["children"] == []


def test_child_summary_has_no_unlinked_fallback(db, other_parent, user):
    with pytest.raises(HTTPException) as exc:
        parents.child_summary(db, other_parent, user)
    assert exc.value.status_code == 404


def test_legacy_dashboard_uses_existing_projection_and_excludes_private_evidence(client, db, parent, other_parent, user):
    db.add_all([
        ParentStudentLink(parent_id=parent.id, student_id=user.id, status=LinkStatus.ACTIVE, scopes={"basic": True, "insights": True}),
        ParentStudentLink(parent_id=other_parent.id, student_id=user.id, status=LinkStatus.ACTIVE, scopes={"basic": True}),
        CareerDNA(user_id=user.id, interests=["Robotics"], sources={"interests": [{"quote": "PRIVATE CHAT EVIDENCE"}]}, novi_reflection="PRIVATE REFLECTION"),
    ])
    db.commit()
    full = client.get("/api/v1/parents/dashboard", headers=auth_header(parent.id, "parent"))
    basic = client.get("/api/v1/parents/dashboard", headers=auth_header(other_parent.id, "parent"))
    assert full.status_code == basic.status_code == 200
    assert full.json()["children"][0]["month_focus"] == ["Robotics"]
    assert basic.json()["children"][0]["month_focus"] == []
    for response in (full, basic):
        assert response.headers["cache-control"] == "no-store"
        assert "PRIVATE" not in response.text


def test_unattached_invitation_cannot_be_approved(db, parent, user):
    invitation = ParentStudentLink(parent_id=parent.id, invited_email=user.email, status=LinkStatus.PENDING)
    db.add(invitation)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        parent_links.approve_link(db, invitation)
    assert exc.value.status_code == 409
    assert invitation.student_id is None and invitation.status == LinkStatus.PENDING


@pytest.mark.parametrize("state", [LinkStatus.PENDING, LinkStatus.REVOKED])
def test_auth_links_hides_nonactive_relationships(client, db, parent, user, pending_link, state):
    pending_link.status = state
    db.commit()
    for identity, role in ((parent, "parent"), (user, "student")):
        response = client.get("/api/v1/auth/links", headers=auth_header(identity.id, role))
        assert response.status_code == 200
        assert response.json() == {"parents": [], "students": []}
        assert response.headers["cache-control"] == "no-store"


def test_auth_links_handles_invitation_only_and_limits_child_metadata(client, db, parent, user, active_link):
    db.add(ParentStudentLink(parent_id=parent.id, invited_email="private-invite@example.com", status=LinkStatus.ACTIVE))
    db.commit()
    response = client.get("/api/v1/auth/links", headers=auth_header(parent.id, "parent"))
    assert response.status_code == 200
    assert response.json() == {"parents": [], "students": [{"id": user.id, "name": user.first_name}]}
    assert user.email not in response.text and user.last_name not in response.text
    assert "private-invite" not in response.text
    student = client.get("/api/v1/auth/links", headers=auth_header(user.id))
    assert student.json()["parents"] == [{"id": parent.id, "name": parent.display_name, "email": parent.email}]


def test_auth_links_never_shows_another_family_or_disabled_child(client, db, parent, other_parent, user, active_link):
    assert client.get("/api/v1/auth/links", headers=auth_header(other_parent.id, "parent")).json() == {"parents": [], "students": []}
    user.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/links", headers=auth_header(parent.id, "parent")).json() == {"parents": [], "students": []}
