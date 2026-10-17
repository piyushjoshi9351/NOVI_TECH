"""Legacy parent invitations and student controls over existing links.

Rules this module exists to enforce:

* ``create_pending_link`` is a legacy service, no longer exposed for public
  requests. New parent-created accounts use ``parent_students`` instead.
* Only unexpired pending links can be approved; revoked links stay revoked.
* Creating a link never reveals whether an email belongs to an existing account
  -- not in the HTTP response, not in the timing, and not in the error messages.
  Both branches return the same generic acknowledgement.
* A raw invite token is generated, handed to the InviteSender, and then only its
  SHA-256 hash is stored.
* Legacy invitation resolution never activates a link and is not invoked by
  signup/login. Expired or revoked invitations cannot be resolved.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
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
    return datetime.now(timezone.utc).replace(tzinfo=None)


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

    Legacy explicit resolution only: auth no longer calls this helper. Only
    unexpired pending invitations may attach, and none are activated.
    """
    normalized = normalize_email(student.email)
    if not normalized or student.role != UserRole.STUDENT or not student.is_active:
        return []

    rows = list(
        db.scalars(
            select(ParentStudentLink).where(
                ParentStudentLink.student_id.is_(None),
                func.lower(func.trim(ParentStudentLink.invited_email)) == normalized,
                ParentStudentLink.status == LinkStatus.PENDING,
            )
        )
    )
    rows = [link for link in rows if not link.is_expired]
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
    """Student approval accepts only an unexpired, attached pending link."""
    try:
        db.refresh(link, with_for_update=True)
        if link.status != LinkStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only pending links can be approved")
        if link.is_expired:
            raise HTTPException(status_code=410, detail="Invitation has expired")
        if link.student_id is None:
            raise HTTPException(status_code=409, detail="Invitation is not attached to a student")
        link.status = LinkStatus.ACTIVE
        link.confirmed_at = _now()
        link.activated_at = link.confirmed_at
        link.activation_source = "student_approved"
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(link)
    return link


def revoke_link(db: Session, link: ParentStudentLink) -> ParentStudentLink:
    """Student (or parent) revokes: access ends immediately."""
    try:
        db.refresh(link, with_for_update=True)
        if link.status == LinkStatus.REVOKED:
            return link
        link.status = LinkStatus.REVOKED
        link.revoked_at = _now()
        db.commit()
    except Exception:
        db.rollback()
        raise
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
