from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.passport import (
    PassportCompletionOut,
    PassportItemCreate,
    PassportItemOut,
    PassportItemUpdate,
)
from app.services import passport as passport_service
from app.services import state_sync

router = APIRouter(prefix="/passport", tags=["passport"])


def _sync(user: User, db: Session) -> None:
    """Keep Letta's state memory in step with any passport mutation."""
    try:
        state_sync.push(user, db)
    except Exception as exc:
        print(f"[sync] passport state push failed: {exc}")


@router.get("", response_model=list[PassportItemOut])
async def list_items(
    category: str | None = None,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return passport_service.list_items(db, user, category=category)


@router.post("/items", response_model=PassportItemOut)
async def create_item(
    data: PassportItemCreate,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    item = passport_service.create_item(db, user, data)
    _sync(user, db)
    return item


@router.patch("/items/{item_id}", response_model=PassportItemOut)
async def update_item(
    item_id: int,
    data: PassportItemUpdate,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    item = passport_service.update_item(db, user, item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Passport item not found")
    _sync(user, db)
    return item


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    if not passport_service.delete_item(db, user, item_id):
        raise HTTPException(status_code=404, detail="Passport item not found")
    _sync(user, db)
    return {"deleted": True}


@router.get("/completion", response_model=PassportCompletionOut)
async def completion(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return passport_service.completion(db, user)


@router.post("/refresh")
async def refresh_from_chat(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    try:
        result = await passport_service.refresh_from_chat(db, user)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _sync(user, db)
    return result
