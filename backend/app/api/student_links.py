"""Student-side control over which parents are following them.

Every route here is scoped to the CALLER's own links: a student can only ever
see and act on links whose ``student_id`` is their own id. There is no path
parameter that selects a student, so there is nothing to tamper with.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.parent import (
    ScopeUpdate,
    StudentLinkList,
    StudentLinkOut,
)
from app.services import parent_links

router = APIRouter(prefix="/student", tags=["parent-links"])


def _require_own_link(db: Session, student: User, link_id: int):
    """Fetch a link, but only if it belongs to the calling student.

    A link id from another student returns 404 rather than 403: the response
    must not confirm that the id exists.
    """
    link = parent_links.get_link(db, link_id)
    if link is None or link.student_id != student.id:
        raise HTTPException(status_code=404, detail="Link not found")
    return link


def _to_out(link) -> StudentLinkOut:
    parent = link.parent
    return StudentLinkOut(
        id=link.id,
        status=link.status.value if hasattr(link.status, "value") else str(link.status),
        label=link.label or "",
        scopes=link.scope_names,
        parent_name=(parent.display_name if parent else "") or "",
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


@router.get("/parent-links", response_model=StudentLinkList)
def list_parent_links(
    student: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Every parent request against this student, pending and active alike.

    Revoked links are excluded -- once withdrawn, a student should not keep
    seeing it in their list.
    """
    from app.models.enums import LinkStatus

    links = [
        _to_out(link)
        for link in parent_links.links_for_student(db, student)
        if link.status != LinkStatus.REVOKED
    ]
    return StudentLinkList(links=links)


@router.post("/parent-links/{link_id}/approve", response_model=StudentLinkOut)
def approve_parent_link(
    link_id: int,
    student: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Consent: pending -> active. This is the only way a parent gains access."""
    link = _require_own_link(db, student, link_id)
    parent_links.approve_link(db, link)
    return _to_out(link)


@router.post("/parent-links/{link_id}/revoke", response_model=StudentLinkOut)
def revoke_parent_link(
    link_id: int,
    student: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Withdraw access. Effective immediately for every parent endpoint."""
    link = _require_own_link(db, student, link_id)
    parent_links.revoke_link(db, link)
    return _to_out(link)


@router.patch("/parent-links/{link_id}/scopes", response_model=StudentLinkOut)
def update_parent_link_scopes(
    link_id: int,
    data: ScopeUpdate,
    student: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Change what this parent may see. ``basic`` is always retained."""
    link = _require_own_link(db, student, link_id)
    parent_links.set_scopes(db, link, {"insights": data.insights, "memory": data.memory})
    return _to_out(link)