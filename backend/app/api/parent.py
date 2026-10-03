"""Parent-facing endpoints.

The ``/students/{student_id}/*`` router is constructed by ``parent_student_router()``
so the authorization dependency (``get_linked_student``) can be attached at the
ROUTER level. That means no handler under it can be added without inheriting the
check -- the default-fastapi footgun of forgetting a dependency on one route is
removed by construction.

Every route that returns student data also sets ``Cache-Control: no-store``: these
are minors' data and must not sit in a shared cache.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_parent, get_linked_student, require_scope
from app.models.user import User
from app.schemas.parent import (
    InsightsResponse,
    MemoryResponse,
    OverviewResponse,
    ParentLinkOut,
    ParentLinkCreated,
    ParentLinkList,
    ParentStudentRef,
    StudentLinkRequest,
)
from app.services import parent_data, parent_links, parent_memory
from app.services.parent_links import GENERIC_INVITE_MESSAGE

router = APIRouter(prefix="/parent", tags=["parent"])

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/students", response_model=ParentLinkList)
def list_my_students(
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Students this parent can currently see.

    Pending requests are listed too (so the UI can show "awaiting approval") but
    carry no student data -- the student hasn't consented, so there is nothing
    about them to return yet.
    """
    payload = [_link_out(link) for link in parent_links.links_for_parent(db, parent)]
    return {"links": payload}


@router.post("/links", response_model=ParentLinkCreated, status_code=201)
def request_link(
    data: StudentLinkRequest,
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Ask to follow a student.

    Always returns the same generic message whether or not the email belongs to
    an existing student, so this cannot be used to test whether an email is
    registered.
    """
    link = parent_links.create_pending_link(db, parent, data.student_email, label=data.label)
    return ParentLinkCreated(
        link_id=link.id,
        status=link.status.value,
        message=GENERIC_INVITE_MESSAGE,
    )


def _link_out(link) -> ParentLinkOut:
    """Serialize a link from the parent's view.

    A pending link's student details stay hidden: ``student`` is only populated
    once the link is ACTIVE.
    """
    is_active = getattr(link.status, "value", link.status) == "active"
    ref = None
    if is_active and link.student is not None:
        ref = ParentStudentRef(
            first_name=link.student.first_name or "",
            grade=link.student.grade,
        )
    return ParentLinkOut(
        id=link.id,
        status=getattr(link.status, "value", str(link.status)),
        label=link.label or "",
        scopes=link.scope_names,
        student=ref,
        # Same gate as `student`: only an active link discloses the id.
        student_id=link.student_id if (is_active and link.student is not None) else None,
        # Never echo the full invited address back to the requester.
        invited_email_first_name=(link.invited_email or "").split("@")[0] or None
        if link.student is None and link.invited_email
        else None,
        created_at=link.created_at,
        expires_at=link.expires_at,
    )


# --------------------------------------------------------------------------- scoped
def parent_student_router() -> APIRouter:
    """Build the per-student router with authorization attached router-wide."""
    scoped = APIRouter(
        prefix="/parent/students/{student_id}",
        tags=["parent"],
        dependencies=[Depends(get_linked_student)],
        responses={404: {"description": "No active link to this student"}},
    )

    @scoped.get("/overview", response_model=OverviewResponse)
    def overview(
        response: Response,
        resolved: tuple = Depends(require_scope("basic")),
        db: Session = Depends(get_db),
    ):
        """``basic`` scope. Goals, roadmap, passport, this week's priorities."""
        student, link = resolved
        response.headers.update(NO_STORE)
        return parent_data.build_overview(db, student, link)

    @scoped.get("/insights", response_model=InsightsResponse)
    def insights(
        response: Response,
        resolved: tuple = Depends(require_scope("insights")),
        db: Session = Depends(get_db),
    ):
        """``insights`` scope. Structured direction only -- no chat evidence."""
        student, link = resolved
        response.headers.update(NO_STORE)
        return parent_data.build_insights(db, student, link)

    @scoped.get("/memory", response_model=MemoryResponse)
    def memory(
        response: Response,
        resolved: tuple = Depends(require_scope("memory")),
    ):
        """``memory`` scope. Read-only, tag-filtered view of the student's Letta memory."""
        student, link = resolved
        response.headers.update(NO_STORE)
        return parent_memory.build_memory(student, link)

    return scoped


parent_scoped_router = parent_student_router()