"""Admin dashboard data access.

Everything here reads the existing ``users`` and ``parent_student_links``
tables only. Mutations are limited to the student ``is_active`` flag and
retrying a failed AI-agent creation attempt; both write an audit log line.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import LinkStatus, UserRole
from app.models.user import ParentStudentLink, User

logger = logging.getLogger("novi.admin")

ACTIVE = "active"
FAILED = "failed"
NOT_CREATED = "not_created"
AGENT_STATUSES = {ACTIVE, FAILED, "pending"}


def agent_status(user: User) -> str:
    """Derive the admin-facing agent status from one place.

    Legacy rows may have a live ``letta_agent_id`` but no ``ai_agent_status``
    because the status column was added later. Treating that as active is
    truthful (the agent exists), while a null id stays ``not_created`` rather
    than being reported as healthy.
    """
    status = (user.ai_agent_status or "").strip().lower()
    if status in AGENT_STATUSES:
        return status
    return ACTIVE if user.letta_agent_id else NOT_CREATED


def _pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size


def _audit(actor_admin_id: int, action: str, target_type: str, target_id: int) -> None:
    """Minimal v1 audit trail: structured log line (no new table this pass)."""
    logger.info(
        "admin_audit actor_admin_id=%s action=%s target_type=%s target_id=%s timestamp=%s",
        actor_admin_id,
        action,
        target_type,
        target_id,
        datetime.now(timezone.utc).isoformat(),
    )


def _student_filters(search: str | None) -> list:
    filters = [User.role == UserRole.STUDENT]
    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        filters.append(
            or_(
                User.email.ilike(like),
                User.first_name.ilike(like),
                User.last_name.ilike(like),
            )
        )
    return filters


def _linked_student_ids(db: Session, student_ids: list[int]) -> set[int]:
    if not student_ids:
        return set()
    rows = db.scalars(
        select(ParentStudentLink.student_id).where(
            ParentStudentLink.student_id.in_(student_ids),
            ParentStudentLink.status == LinkStatus.ACTIVE,
        )
    )
    return {sid for sid in rows if sid is not None}


def _student_out(user: User, has_linked_parent: bool) -> dict:
    return {
        "id": user.id,
        "name": user.display_name,
        "email": user.email,
        "grade": user.grade,
        "school": user.school,
        "is_active": bool(user.is_active),
        "created_at": user.created_at,
        "has_linked_parent": has_linked_parent,
    }


def _parent_out(user: User, linked_children_count: int) -> dict:
    return {
        "id": user.id,
        "name": user.display_name,
        "email": user.email,
        "is_active": bool(user.is_active),
        "created_at": user.created_at,
        "linked_children_count": linked_children_count,
    }


def _mentor_out(user: User) -> dict:
    return {
        "student_id": user.id,
        "name": user.display_name,
        "email": user.email,
        "agent_id": user.letta_agent_id,
        "status": agent_status(user),
        "attempts": user.ai_agent_attempts or 0,
        "updated_at": user.updated_at,
    }


def _student_or_404(db: Session, student_id: int) -> User:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.STUDENT:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def _parent_or_404(db: Session, parent_id: int) -> User:
    parent = db.get(User, parent_id)
    if parent is None or parent.role != UserRole.PARENT:
        raise HTTPException(status_code=404, detail="Parent not found")
    return parent


def dashboard(db: Session) -> dict:
    student = User.role == UserRole.STUDENT
    active_agent = or_(
        User.ai_agent_status == ACTIVE,
        and_(
            or_(User.ai_agent_status.is_(None), User.ai_agent_status == ""),
            User.letta_agent_id.isnot(None),
        ),
    )
    since = datetime.now(timezone.utc) - timedelta(days=7)

    def count(*filters) -> int:
        return int(db.scalar(select(func.count(User.id)).where(*filters)) or 0)

    return {
        "total_students": count(student),
        "total_parents": count(User.role == UserRole.PARENT),
        "active_students": count(student, User.is_active.is_(True)),
        "active_ai_mentors": count(student, active_agent),
        "new_registrations_7d": count(User.created_at >= since),
    }


def list_students(db: Session, search: str | None, page: int, page_size: int) -> dict:
    filters = _student_filters(search)
    total = int(db.scalar(select(func.count(User.id)).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    linked = _linked_student_ids(db, [u.id for u in rows])
    return {
        "items": [_student_out(u, u.id in linked) for u in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def get_student(db: Session, student_id: int) -> dict:
    student = _student_or_404(db, student_id)
    rows = db.execute(
        select(ParentStudentLink, User)
        .join(User, User.id == ParentStudentLink.parent_id)
        .where(ParentStudentLink.student_id == student_id)
        .order_by(ParentStudentLink.created_at.desc(), ParentStudentLink.id.desc())
    ).all()
    linked_parents = [
        {
            "id": parent.id,
            "name": parent.display_name,
            "email": parent.email,
            "status": link.status.value if hasattr(link.status, "value") else str(link.status),
            "linked_at": link.created_at,
        }
        for link, parent in rows
    ]
    active_parent = any(p["status"] == LinkStatus.ACTIVE.value for p in linked_parents)
    return {
        **_student_out(student, active_parent),
        "linked_parents": linked_parents,
    }


def set_student_status(db: Session, admin: User, student_id: int, is_active: bool) -> dict:
    student = _student_or_404(db, student_id)
    student.is_active = is_active
    db.commit()
    _audit(
        admin.id,
        "student.activated" if is_active else "student.deactivated",
        "student",
        student.id,
    )
    return get_student(db, student_id)


def list_parents(db: Session, page: int, page_size: int) -> dict:
    filters = [User.role == UserRole.PARENT]
    total = int(db.scalar(select(func.count(User.id)).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    parent_ids = [u.id for u in rows]
    counts: dict[int, int] = {}
    if parent_ids:
        counts = {
            parent_id: count
            for parent_id, count in db.execute(
                select(ParentStudentLink.parent_id, func.count(ParentStudentLink.id))
                .where(
                    ParentStudentLink.parent_id.in_(parent_ids),
                    ParentStudentLink.status == LinkStatus.ACTIVE,
                )
                .group_by(ParentStudentLink.parent_id)
            ).all()
        }
    return {
        "items": [_parent_out(u, counts.get(u.id, 0)) for u in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def get_parent(db: Session, parent_id: int) -> dict:
    parent = _parent_or_404(db, parent_id)
    rows = db.execute(
        select(ParentStudentLink, User)
        .join(User, User.id == ParentStudentLink.student_id)
        .where(ParentStudentLink.parent_id == parent_id)
        .order_by(ParentStudentLink.created_at.desc(), ParentStudentLink.id.desc())
    ).all()
    linked_children = [
        {
            "id": child.id,
            "name": child.display_name,
            "email": child.email,
            "grade": child.grade,
            "status": link.status.value if hasattr(link.status, "value") else str(link.status),
            "linked_at": link.created_at,
        }
        for link, child in rows
    ]
    active_count = sum(1 for c in linked_children if c["status"] == LinkStatus.ACTIVE.value)
    return {
        **_parent_out(parent, active_count),
        "linked_children": linked_children,
    }


def list_ai_mentors(db: Session, page: int, page_size: int) -> dict:
    filters = [User.role == UserRole.STUDENT]
    total = int(db.scalar(select(func.count(User.id)).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [_mentor_out(u) for u in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def retry_agent(db: Session, admin: User, student_id: int) -> dict:
    student = _student_or_404(db, student_id)
    if agent_status(student) != FAILED:
        raise HTTPException(status_code=400, detail="Only a failed AI agent can be retried")

    student.ai_agent_attempts = (student.ai_agent_attempts or 0) + 1
    db.commit()

    from app.services.chat import _lazy_ensure_agent

    _lazy_ensure_agent(student, db, record_attempt=False)
    db.refresh(student)
    _audit(admin.id, "ai_agent.retried", "student", student.id)
    return _mentor_out(student)
