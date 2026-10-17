from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_parent
from app.models.user import User
from app.schemas.dashboard import ParentDashboardOut
from app.schemas.parent import AdvisorAsk, AdvisorResponse
from app.services import parents as parent_service

router = APIRouter(prefix="/parents", tags=["parents"])


@router.post("/link", deprecated=True)
async def link_student(
    parent: User = Depends(get_current_parent),
):
    """Retired legacy email-link flow."""
    raise HTTPException(
        status_code=410,
        detail="Access requests are retired. Create a child with POST /api/v1/parent/students",
    )


@router.get("/dashboard", response_model=ParentDashboardOut)
async def parent_dashboard(response: Response, parent: User = Depends(get_current_parent), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return parent_service.parent_dashboard(db, parent)  # type: ignore[arg-type]


@router.post("/advisor", response_model=AdvisorResponse)
async def advisor(
    data: AdvisorAsk,
    response: Response,
    parent: User = Depends(get_current_parent),
    db: Session = Depends(get_db),
):
    # A parent question is untrusted text headed for an LLM prompt: bounded by
    # the schema's max_length and rate limited per parent. `history` carries the
    # same guarantees (bounded turns, whitelisted roles) and is used only for
    # this one answer -- nothing is written.
    try:
        parent_service.check_rate_limit(parent.id)
    except parent_service.RateLimited:
        raise HTTPException(
            status_code=429,
            detail="Too many questions at once — please wait a moment.",
        )

    answer = await parent_service.advisor(
        db, parent, data.question, data.child_id, history=data.history
    )
    response.headers.update({"Cache-Control": "no-store"})
    return AdvisorResponse(answer=answer)
