"""Atomic creation of a student account and its creating parent's active link."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import LinkStatus, UserRole
from app.models.user import DEFAULT_LINK_SCOPES, ParentStudentLink, User
from app.schemas.parent import ParentStudentCreate, ParentStudentCreated


def _duplicate_email(error: IntegrityError) -> bool:
    """Recognize MySQL and SQLite email uniqueness failures only."""
    message = str(error.orig).lower()
    mysql_duplicate = bool(error.orig.args) and error.orig.args[0] == 1062
    return (mysql_duplicate and "email" in message) or (
        "unique constraint failed: users.email" in message
    )


def create_student(
    db: Session, parent: User, data: ParentStudentCreate
) -> ParentStudentCreated:
    if parent.role != UserRole.PARENT or not parent.is_active:
        raise HTTPException(status_code=403, detail="Parent access required")
    email = str(data.email).strip().lower()
    if email == parent.email.strip().lower():
        raise HTTPException(status_code=400, detail="Child email must differ from the parent's email")

    # Authentication has already begun this request's session transaction.
    # Flush assigns IDs without committing; a link failure rolls back the user.
    try:
        student = User(
            email=email,
            password_hash=hash_password(data.password.get_secret_value()),
            role=UserRole.STUDENT,
            first_name=data.name,
            must_change_password=True,
            token_version=0,
            created_by_parent_id=parent.id,
        )
        db.add(student)
        db.flush()
        link = ParentStudentLink(
            parent_id=parent.id,
            student_id=student.id,
            status=LinkStatus.ACTIVE,
            scopes=dict(DEFAULT_LINK_SCOPES),
            activation_source="parent_created",
            activated_at=datetime.now(timezone.utc),
            # Automatic activation is not student approval.
            confirmed_at=None,
        )
        db.add(link)
        db.flush()
        receipt = ParentStudentCreated(
            student_id=student.id,
            link_id=link.id,
            name=student.display_name,
            status=link.status.value,
            scopes=link.scope_names,
            activated_at=link.activated_at,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _duplicate_email(exc):
            raise HTTPException(status_code=409, detail="Email already registered") from None
        raise
    except Exception:
        db.rollback()
        raise

    # No token issuance or invitation resolution. Letta continues to provision
    # lazily on first use, outside this account/link transaction.
    return receipt
