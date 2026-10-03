"""Consent-link lifecycle: pending -> active -> revoked, and invitation resolution.

These are the rules that make parent access legitimate, so they are tested at the
service layer (no HTTP) to isolate the state machine.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.enums import LinkStatus
from app.models.user import DEFAULT_LINK_SCOPES, ParentStudentLink, hash_invite_token
from app.services import parent_links
from app.services.parent_invites import InviteSender
from tests.conftest import auth_header


class RecordingSender(InviteSender):
    def __init__(self):
        self.sent = []

    def send_parent_invite(self, *, to_email, parent_name, raw_token, expires_at):
        self.sent.append({"to": to_email, "raw_token": raw_token, "expires_at": expires_at})
        return True


class BrokenSender(InviteSender):
    def send_parent_invite(self, **kwargs):
        raise RuntimeError("smtp is down")


# ------------------------------------------------------------------ creation
def test_link_to_existing_student_is_pending_not_active(db, parent, user):
    link = parent_links.create_pending_link(db, parent, user.email)
    assert link.status == LinkStatus.PENDING
    assert link.student_id == user.id
    assert link.scopes == DEFAULT_LINK_SCOPES


def test_link_to_unknown_email_is_invitation_only(db, parent):
    link = parent_links.create_pending_link(db, parent, "ghost@nowhere.test")
    assert link.student_id is None
    assert link.invited_email == "ghost@nowhere.test"
    assert link.status == LinkStatus.PENDING


def test_email_is_normalized(db, parent, user):
    link = parent_links.create_pending_link(db, parent, "  STUDENT@Example.COM ")
    assert link.student_id == user.id
    assert link.invited_email == user.email


def test_non_student_role_is_not_treated_as_a_student(db, parent, other_parent):
    """A parent email must not resolve to the parent account as a student."""
    link = parent_links.create_pending_link(db, parent, other_parent.email)
    assert link.student_id is None
    assert link.status == LinkStatus.PENDING


def test_only_token_hash_is_persisted(db, parent):
    sender = RecordingSender()
    link = parent_links.create_pending_link(
        db, parent, "ghost@nowhere.test", sender=sender
    )
    raw = sender.sent[0]["raw_token"]
    assert link.invite_token_hash == hash_invite_token(raw)
    assert link.invite_token_hash != raw
    assert raw not in str(link.invite_token_hash)


def test_invite_expires_in_14_days(db, parent):
    link = parent_links.create_pending_link(db, parent, "ghost@nowhere.test")
    delta = link.expires_at - datetime.now()
    assert timedelta(days=13, hours=23) < delta <= timedelta(days=14)


def test_no_invite_email_when_student_exists(db, parent, user):
    sender = RecordingSender()
    parent_links.create_pending_link(db, parent, user.email, sender=sender)
    assert sender.sent == []


def test_duplicate_request_reuses_the_same_link(db, parent, user):
    first = parent_links.create_pending_link(db, parent, user.email)
    second = parent_links.create_pending_link(db, parent, user.email)
    assert first.id == second.id
    rows = db.scalars(
        select(ParentStudentLink).where(ParentStudentLink.parent_id == parent.id)
    ).all()
    assert len(rows) == 1


def test_two_parents_can_request_the_same_student(db, parent, other_parent, user):
    a = parent_links.create_pending_link(db, parent, user.email)
    b = parent_links.create_pending_link(db, other_parent, user.email)
    assert a.id != b.id


def test_invite_sender_failure_does_not_break_the_link(db, parent):
    link = parent_links.create_pending_link(
        db, parent, "ghost@nowhere.test", sender=BrokenSender()
    )
    assert link.id is not None
    assert link.status == LinkStatus.PENDING


def test_empty_email_rejected(db, parent):
    with pytest.raises(ValueError):
        parent_links.create_pending_link(db, parent, "   ")


# ------------------------------------------------------------------ resolution
def test_invitation_resolves_on_verified_signup_but_stays_pending(db, parent):
    pending = parent_links.create_pending_link(db, parent, "newkid@nowhere.test")

    from app.models.user import User

    student = User(
        email="newkid@nowhere.test", password_hash="x", first_name="New", grade=9
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    resolved = parent_links.resolve_invitations_for_student(db, student)
    assert len(resolved) == 1
    db.refresh(pending)
    assert pending.student_id == student.id
    assert pending.status == LinkStatus.PENDING, "resolution must not auto-activate"


def test_resolution_is_case_and_whitespace_insensitive(db, parent):
    parent_links.create_pending_link(db, parent, "kid@nowhere.test")

    from app.models.user import User

    student = User(email="KID@NOWHERE.TEST", password_hash="x", first_name="K")
    db.add(student)
    db.commit()
    db.refresh(student)

    assert parent_links.resolve_invitations_for_student(db, student)


def test_resolution_ignores_other_emails(db, parent, user):
    from app.models.user import User

    stranger = User(email="someone@else.test", password_hash="x")
    db.add(stranger)
    db.commit()
    db.refresh(stranger)
    assert parent_links.resolve_invitations_for_student(db, stranger) == []


# ------------------------------------------------------------------ lifecycle
def test_approve_activates_and_stamps_confirmed_at(db, pending_link):
    link = parent_links.approve_link(db, pending_link)
    assert link.status == LinkStatus.ACTIVE
    assert link.confirmed_at is not None


def test_revoke_ends_access(db, active_link):
    link = parent_links.revoke_link(db, active_link)
    assert link.status == LinkStatus.REVOKED
    assert link.revoked_at is not None
    assert parent_links.active_link_for(db, active_link.parent, active_link.student_id) is None


def test_active_link_lookup_ignores_pending_and_revoked(db, parent, user, pending_link):
    assert parent_links.active_link_for(db, parent, user.id) is None
    parent_links.approve_link(db, pending_link)
    assert parent_links.active_link_for(db, parent, user.id) is not None
    parent_links.revoke_link(db, pending_link)
    assert parent_links.active_link_for(db, parent, user.id) is None


def test_revoke_is_idempotent(db, active_link):
    parent_links.revoke_link(db, active_link)
    again = parent_links.revoke_link(db, active_link)
    assert again.status == LinkStatus.REVOKED


# ------------------------------------------------------------------ scopes
def test_scopes_default_to_basic_only(db, pending_link):
    assert pending_link.scopes == {"basic": True}
    assert pending_link.scope_names == ["basic"]


def test_set_scopes_always_keeps_basic(db, active_link):
    link = parent_links.set_scopes(db, active_link, {"insights": True, "memory": False})
    assert link.scopes == {"basic": True, "insights": True, "memory": False}
    assert link.scope_names == ["basic", "insights"]


def test_set_scopes_drops_unknown_keys(db, active_link):
    link = parent_links.set_scopes(db, active_link, {"insights": True, "secrets": True})
    assert "secrets" not in link.scopes


def test_set_scopes_cannot_grant_nothing(db, active_link):
    link = parent_links.set_scopes(db, active_link, {})
    assert link.has_scope("basic") is True


def test_has_scope_rejects_unknown_scope(db, active_link):
    assert active_link.has_scope("everything") is False


# ------------------------------------------------------------------ expiry
def test_expired_invitation_reports_expired(db, parent):
    link = parent_links.create_pending_link(db, parent, "ghost@nowhere.test")
    link.expires_at = datetime.now() - timedelta(days=1)
    db.commit()
    db.refresh(link)
    assert link.is_expired is True


def test_claimed_link_never_expires(db, active_link):
    active_link.expires_at = datetime.now() - timedelta(days=400)
    db.commit()
    db.refresh(active_link)
    assert active_link.is_expired is False


# ------------------------------------------------------------------ listings
def test_links_for_student_includes_invitation(db, parent, user):
    invitation = parent_links.create_pending_link(db, parent, user.email)
    invitation.student_id = None
    db.commit()
    db.refresh(invitation)

    found = parent_links.links_for_student(db, user)
    assert [link.id for link in found] == [invitation.id]


def test_links_for_student_excludes_other_students(db, pending_link, other_student):
    assert parent_links.links_for_student(db, other_student) == []

# ------------------------------------------------------- legacy /parents/link
def test_legacy_link_endpoint_reports_pending_not_linked(client, parent, user):
    """The pre-existing parent overview page still POSTs /parents/link.

    It must not 500 and must not claim success, because the link now needs the
    student's approval.
    """
    r = client.post(
        "/api/v1/parents/link",
        json={"student_email": user.email},
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pending"] is True
    assert body["linked"] is False
    assert body["student"]["name"] == user.display_name


def test_legacy_link_endpoint_survives_an_unknown_email(client, parent):
    """Regression: an unknown email used to 500 because the route dereferenced
    a `None` student."""
    r = client.post(
        "/api/v1/parents/link",
        json={"student_email": "nobody@nowhere.test"},
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["student"] is None
    assert body["pending"] is True


def test_legacy_link_endpoint_does_not_probe_for_known_emails(client, parent, user):
    known = client.post(
        "/api/v1/parents/link",
        json={"student_email": user.email},
        headers=auth_header(parent.id, "parent"),
    ).json()
    unknown = client.post(
        "/api/v1/parents/link",
        json={"student_email": "nobody@nowhere.test"},
        headers=auth_header(parent.id, "parent"),
    ).json()
    assert known["message"] == unknown["message"]


def test_legacy_dashboard_hides_a_pending_student(client, parent, user):
    client.post(
        "/api/v1/parents/link",
        json={"student_email": user.email},
        headers=auth_header(parent.id, "parent"),
    )
    r = client.get("/api/v1/parents/dashboard", headers=auth_header(parent.id, "parent"))
    assert r.status_code == 200
    assert all(c["name"] != user.display_name for c in r.json()["children"])

def test_row_built_without_scopes_still_grants_basic(db, parent, user):
    """The ORM default must not be {}: granted_scopes() reads a missing key as
    "not shared", so a direct insert would otherwise lock the parent out of the
one scope that is never optional."""
    link = ParentStudentLink(
        parent_id=parent.id,
        student_id=user.id,
        status=LinkStatus.ACTIVE,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    assert link.scope_names == ["basic"]
    assert link.has_scope("basic") is True
