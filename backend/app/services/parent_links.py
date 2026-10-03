"""Parent <-> student linking, built around student consent.

Rules this module exists to enforce:

* A link is NEVER created as active. ``create_pending_link`` always produces
  ``pending``; only the student can approve (or revoke) it.
* Creating a link never reveals whether an email belongs to an existing account
  -- not in the HTTP response, not in the timing, and not in the error messages.
  Both branches return the same generic acknowledgement.
* A raw invite token is generated, handed to the InviteSender, and then only its
  SHA-256 hash is stored.
* Invitation-only links (parent typed an email with no account) are resolved on
  the student's first VERIFIED signup/login by matching their verified email.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LinkStatus, UserRole
from app.models.user import (
    DEFAULT_LINK_SCOPES,
    INVITE_TTL_DAYS,
    LINK_SCOPES,
    ParentStudentLink,
    User,
    hash_invite_token,
    new_invite_token,
)
from app.services.parent_invites import InviteSender, get_invite_sender

logger = logging.getLogger("novi.parent_links")

# The single acknowledgement for every successful invite attempt, regardless of
# whether the student account exists. Deliberately vague on purpose.
GENERIC_INVITE_MESSAGE = "If this student has a Novi account, we've sent them a request"


def normalize_email(email: str) -> str:
    """Canonical form used for every link lookup. Case-insensitive, trimmed."""
    return (email or "").strip().lower()


def _now() -> datetime:
    return datetime.now()


def _expiry() -> datetime:
    return _now() + timedelta(days=INVITE_TTL_DAYS)


def get_link(db: Session, link_id: int) -> ParentStudentLink | None:
    return db.scalar(select(ParentStudentLink).where(ParentStudentLink.id == link_id))


def active_link_for(db: Session, parent: User, student_id: int) -> ParentStudentLink | None:
    """The parent's ACTIVE link to a student, or None.

    Every parent-facing data read funnels through this, so revoked and pending
    links are invisible by construction.
    """
    return db.scalar(
        select(ParentStudentLink).where(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == LinkStatus.ACTIVE,
        )
    )


def links_for_parent(db: Session, parent: User) -> list[ParentStudentLink]:
    """Every link this parent owns, newest first."""
    return list(
        db.scalars(
            select(ParentStudentLink)
            .where(ParentStudentLink.parent_id == parent.id)
            .order_by(ParentStudentLink.created_at.desc(), ParentStudentLink.id.desc())
        )
    )


def links_for_student(db: Session, student: User) -> list[ParentStudentLink]:
    """Every link awaiting or held against this student.

    Includes invitation-only links whose ``invited_email`` matches the student,
    so a claim can be reviewed before the student claims it.
    """
    return list(
        db.scalars(
            select(ParentStudentLink)
            .where(
                (ParentStudentLink.student_id == student.id)
                | (
                    (ParentStudentLink.student_id.is_(None))
                    & (ParentStudentLink.invited_email == normalize_email(student.email))
                )
            )
            .order_by(ParentStudentLink.created_at.desc(), ParentStudentLink.id.desc())
        )
    )


def create_pending_link(
    db: Session,
    parent: User,
    student_email: str,
    *,
    label: str | None = None,
    sender: InviteSender | None = None,
) -> ParentStudentLink:
    """Create a PENDING link from ``parent`` to ``student_email``.

    Never activates. Never discloses whether the student exists:

    * existing student account -> link with ``student_id`` set, still pending,
      so the student approves it in-app.
    * no account / wrong role -> invitation-only link (``student_id`` NULL) with
      ``invited_email`` set and an expiring token; resolved on first verified
      signup or login.

    Re-inviting the same target returns the existing pending link rather than
    creating a duplicate.
    """
    email = normalize_email(student_email)
    if not email:
        raise ValueError("student_email is required")

    student = db.scalar(
        select(User).where(User.email == email, User.role == UserRole.STUDENT)
    )

    # Idempotency: never stack duplicate requests for the same target.
    if student is not None:
        existing = db.scalar(
            select(ParentStudentLink).where(
                ParentStudentLink.parent_id == parent.id,
                ParentStudentLink.student_id == student.id,
            )
        )
        if existing is not None:
            return existing
    else:
        existing = db.scalar(
            select(ParentStudentLink).where(
                ParentStudentLink.parent_id == parent.id,
                ParentStudentLink.invited_email == email,
            )
        )
        if existing is not None:
            return existing

    raw_token = new_invite_token()
    link = ParentStudentLink(
        parent_id=parent.id,
        student_id=student.id if student is not None else None,
        status=LinkStatus.PENDING,
        label=(label or "Child").strip()[:100] or "Child",
        scopes=dict(DEFAULT_LINK_SCOPES),
        invited_email=email,
        invite_token_hash=hash_invite_token(raw_token),
        expires_at=_expiry(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    # A raw token is emailed only for invitation-only links: an existing student
    # approves in-app and does not need an emailed link.
    if student is None:
        try:
            (sender or get_invite_sender()).send_parent_invite(
                to_email=email,
                parent_name=parent.display_name,
                raw_token=raw_token,
                expires_at=link.expires_at,
            )
        except Exception:
            # Delivery is best-effort: the link still exists and can be
            # re-requested. Never surface provider errors to the caller.
            logger.exception("failed to deliver parent invite for link %s", link.id)

    logger.info("pending parent link %s created (parent=%s)", link.id, parent.id)
    return link


def resolve_invitations_for_student(db: Session, student: User) -> list[ParentStudentLink]:
    """Attach invitation-only links to a now-verified student account.

    Called on email-verified signup, first login, and Google signup/login. Only
    ``student_id`` is set -- the link stays ``pending``, so the student still has
    to approve before the parent sees anything.
    """
    normalized = normalize_email(student.email)
    if not normalized:
        return []

    rows = list(
        db.scalars(
            select(ParentStudentLink).where(
                ParentStudentLink.student_id.is_(None),
                ParentStudentLink.invited_email == normalized,
            )
        )
    )
    if not rows:
        return []

    for link in rows:
        link.student_id = student.id
    db.commit()
    for link in rows:
        db.refresh(link)
    logger.info("resolved %s invitation(s) for student %s", len(rows), student.id)
    return rows


def approve_link(db: Session, link: ParentStudentLink) -> ParentStudentLink:
    """Student approves: pending -> active, granting the default scopes."""
    if link.status == LinkStatus.ACTIVE:
        return link
    link.status = LinkStatus.ACTIVE
    link.confirmed_at = _now()
    link.revoked_at = None
    if not isinstance(link.scopes, dict) or not link.scopes:
        link.scopes = dict(DEFAULT_LINK_SCOPES)
    db.commit()
    db.refresh(link)
    return link


def revoke_link(db: Session, link: ParentStudentLink) -> ParentStudentLink:
    """Student (or parent) revokes: access ends immediately."""
    if link.status == LinkStatus.REVOKED:
        return link
    link.status = LinkStatus.REVOKED
    link.revoked_at = _now()
    db.commit()
    db.refresh(link)
    return link


def set_scopes(db: Session, link: ParentStudentLink, scopes: dict[str, bool]) -> ParentStudentLink:
    """Replace the link's sharing consent, filtered to the known allowlist.

    ``basic`` cannot be revoked: without it a parent sees nothing, and the
    relationship itself is the grant.
    """
    sanitized: dict[str, bool] = {}
    for name in LINK_SCOPES:
        if name == "basic":
            continue
        sanitized[name] = scopes.get(name) is True
    sanitized["basic"] = True
    link.scopes = {name: sanitized[name] for name in LINK_SCOPES}
    db.commit()
    db.refresh(link)
    return link