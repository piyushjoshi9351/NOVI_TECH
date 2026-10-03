from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_parent
from app.models.enums import LinkStatus
from app.models.user import User
from app.schemas.dashboard import ParentDashboardOut
from app.schemas.parent import AdvisorAsk, AdvisorResponse, LinkStudentRequest
from app.services import parents as parent_service
from app.services.parent_links import GENERIC_INVITE_MESSAGE

router = APIRouter(prefix="/parents", tags=["parents"])


@router.post("/link")
async def link_student(
    data: LinkStudentRequest,
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    """Legacy entry point used by the existing parent overview page.

    Linking is now consent-based, so this creates a PENDING request that the
    student must approve. The response therefore reports `pending` and only
    includes the student when the account already exists -- and it deliberately
    does not distinguish "no such student" from "invited", so it cannot be used
    to probe whether an email is registered.
    """
    link = parent_service.request_link(db, parent, data.student_email)
    return {
        "linked": link.status == LinkStatus.ACTIVE,
        "pending": link.status == LinkStatus.PENDING,
        "student": (
            {"id": link.student.id, "name": link.student.display_name}
            if link.student is not None
            else None
        ),
        "message": GENERIC_INVITE_MESSAGE,
    }


@router.get("/dashboard", response_model=ParentDashboardOut)
async def parent_dashboard(parent: User = Depends(get_current_parent), db: Session = Depends(get_db)):
    return parent_service.parent_dashboard(db, parent)  # type: ignore[arg-type]


@router.post("/advisor", response_model=AdvisorResponse)
async def advisor(
    data: AdvisorAsk,
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    answer = await parent_service.advisor(db, parent, data.question, data.child_id)
    return AdvisorResponse(answer=answer)