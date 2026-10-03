from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.checkin import CheckinCreate, CheckinOut, CheckinSummaryOut, ContributionGraphOut
from app.services import checkins as checkin_service
from app.services import state_sync

router = APIRouter(prefix="/checkins", tags=["check-ins"])


def _sync(user: User, db: Session) -> None:
    """Keep Letta's state memory in step with any check-in change."""
    try:
        state_sync.push(user, db)
    except Exception as exc:
        print(f"[sync] checkin state push failed: {exc}")


@router.get("", response_model=list[CheckinOut])
async def list_checkins(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return checkin_service.list_checkins(db, user)


@router.get("/current", response_model=CheckinOut)
async def current_checkin(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return checkin_service.get_or_create_current(db, user)


@router.post("", response_model=CheckinOut)
async def save_checkin(
    data: CheckinCreate,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    result = checkin_service.save_answers(db, user, data)
    _sync(user, db)
    return result


@router.get("/graph", response_model=ContributionGraphOut)
async def contribution_graph(
    weeks: int = 53,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return checkin_service.contribution_graph(db, user, weeks)


@router.post("/summarize", response_model=CheckinOut)
async def summarize_checkin(
    checkin_id: int | None = None,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    result = await checkin_service.summarize(db, user, checkin_id)
    _sync(user, db)
    return result

# The planner shares the check-in service and the same student ownership checks.
import datetime
from app.schemas.planner import DailyCheckinSave, ScheduleBlockCreate
from fastapi import HTTPException


@router.get('/planner/day')
def planner_day(date: datetime.date | None = None, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return checkin_service.get_day(db, user, date)


@router.post('/planner/day/auto-plan')
def planner_auto_plan(date: datetime.date | None = None, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return checkin_service.auto_plan(db, user, date or datetime.date.today())


@router.post('/planner/day/checkin')
def planner_checkin(data: DailyCheckinSave, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    checkin_service.save_daily_checkin(db, user, data)
    return checkin_service.get_day(db, user, data.date)


@router.post('/planner/blocks')
def planner_create_block(data: ScheduleBlockCreate, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return checkin_service.create_block(db, user, data)


@router.patch('/planner/blocks/{block_id}')
def planner_toggle_block(block_id: int, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    block = checkin_service.toggle_block(db, user, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail='Planner block not found')
    return block


@router.delete('/planner/blocks/{block_id}')
def planner_delete_block(block_id: int, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    if not checkin_service.delete_block(db, user, block_id):
        raise HTTPException(status_code=404, detail='Planner block not found')
    return {'deleted': True}
