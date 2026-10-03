from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import LinkStatus
from app.models.user import LINK_SCOPES, ParentStudentLink, User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def _get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # A forged/non-numeric sub would otherwise raise ValueError -> 500.
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_current_user(
    user: User = Depends(_get_current_user),
) -> User:
    return user


def get_current_student(
    user: User = Depends(_get_current_user),
) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Student access required")
    return user


def get_current_parent(
    user: User = Depends(_get_current_user),
) -> User:
    if user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail="Parent access required")
    return user


# --------------------------------------------------------------------------- parents
# Authorization for every /parent/students/{student_id}/* endpoint.
#
# The single most important property here: the link is looked up by
# (current_parent.id, {student_id}) from the DATABASE, never by trusting the
# path parameter on its own. A parent who guesses another family's student_id
# gets a 404 -- indistinguishable from "no such student", so this endpoint cannot
# be used to probe for valid student ids.


def get_linked_student(
    student_id: int,
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
) -> tuple[User, ParentStudentLink]:
    """Resolve a path student_id to (student, link) for the CURRENT parent.

    This is THE single authorization function for parent data. Every
    ``/parent/students/{student_id}/*`` route depends on it (attached at router
    level in ``app/api/parent.py``), so no handler can be added without
    inheriting the check.

    It verifies, in order:
      1. the caller holds the ``parent`` role (``get_current_parent`` -> 403),
      2. an ACTIVE link from THIS parent to THIS student exists,
      3. the student exists, is a student, and is active.

    Failures raise 404 (not 403) so a guessed or foreign student_id is
    indistinguishable from "no such student" -- the endpoint cannot be used to
    enumerate ids, and a revoked link loses access immediately rather than
    being filtered out further downstream.

    Which SECTIONS are consented is NOT an error condition here: it is read off
    ``link`` and applied inside the projection
    (``app.services.parent_projection``), so an unshared section renders as
    "hasn't shared this" instead of a failed request.
    """
    link = db.scalar(
        select(ParentStudentLink)
        .where(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == LinkStatus.ACTIVE,
        )
        .limit(1)
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Student not found")

    student = db.get(User, student_id)
    if student is None or student.role != UserRole.STUDENT or not student.is_active:
        raise HTTPException(status_code=404, detail="Student not found")

    return student, link


# The name the rest of the codebase (and the docs) refers to. Same function --
# kept as an explicit alias rather than a second implementation, so there is
# exactly one place authorization can live.
get_authorized_link = get_linked_student


def require_scope(scope: str):
    """Build a dependency factory asserting the link grants ``scope``.

    Retained for any route that wants a hard 403 on a missing section. The
    dashboard itself does NOT use this -- unshared sections are rendered as
    empty, not as errors (see ``get_linked_student`` and the projection).

    An unknown scope name is a programming error and raises at import time
    rather than silently granting access.
    """
    if scope not in LINK_SCOPES:
        raise ValueError(f"Unknown link scope: {scope!r}")

    def _dependency(
        resolved: tuple[User, ParentStudentLink] = Depends(get_linked_student),
    ) -> tuple[User, ParentStudentLink]:
        _student, link = resolved
        if not link.has_scope(scope):
            raise HTTPException(
                status_code=403,
                detail=f"This student has not shared their {scope} with you",
            )
        return resolved

    return _dependency