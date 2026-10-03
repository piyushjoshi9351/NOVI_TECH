import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.career_dna import CareerDNAOut, CareerDNAUpdate, MagicDNARequest, ReflectionUpdate
from app.services import career_dna as dna_service

router = APIRouter(prefix="/dna", tags=["career-dna"])


@router.get("", response_model=CareerDNAOut)
async def get_dna(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    dna = dna_service.get_or_create_dna(user, db)
    return _payload(dna)


@router.patch("", response_model=CareerDNAOut)
async def update_dna(
    data: CareerDNAUpdate,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    dna = dna_service.update_dna(user, data, db)
    return _payload(dna)


@router.post("/magic", response_model=CareerDNAOut)
async def magic_dna(
    data: MagicDNARequest,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    text = (data.text or "").strip()
    if len(text) < 12:
        raise HTTPException(status_code=422, detail="Tell Novi a little more about yourself first")
    try:
        dna = await dna_service.build_dna_from_text(user, text, db)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    from app.services.state_sync import push as push_state
    push_state(user, db)
    return _payload(dna)


@router.post("/refresh", response_model=CareerDNAOut)
async def refresh_dna(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    conv_id, chat_history = _recent_history(user, db)
    if not chat_history:
        raise HTTPException(status_code=400, detail="Chat with Novi first so your DNA has something to learn from")
    try:
        dna = await asyncio.wait_for(dna_service.refresh_dna_from_history(user, chat_history, db, conversation_id=conv_id), timeout=90)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="DNA refresh took too long. Please retry shortly.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _payload(dna)


@router.post("/reflect", response_model=CareerDNAOut)
async def reflect(
    data: ReflectionUpdate,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    dna = dna_service.reflect_dna(user, data, db)
    return _payload(dna)


@router.get("/context")
async def dna_context(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return dna_service.dna_context(user, db)


def _payload(dna) -> dict:
    return {
        "id": dna.id,
        "user_id": dna.user_id,
        "traits": dna.traits or [],
        "motivations": dna.motivations or [],
        "strengths": dna.strengths or [],
        "development_areas": dna.development_areas or [],
        "interests": dna.interests or [],
        "subjects": dna.subjects or [],
        "skills": dna.skills or [],
        "career_zones": dna.career_zones or [],
        "values": dna.values or [],
        "goals": dna.goals or [],
        "novi_reflection": dna.novi_reflection or "",
        "dna_filled": dna.dna_filled,
        "updated_at": dna.updated_at.isoformat() if dna.updated_at else None,
        "sources": dna.sources or {},
        "excluded": dna.excluded or [],
    }


def _recent_history(user: User, db: Session) -> tuple[int | None, list[dict]]:
    from sqlalchemy import select
    from app.models.chat import Conversation, Message
    from app.models.enums import MessageRole
    from app.routers.onboarding import _finalize_history

    # Preserve chronology across conversations and keep the newest messages.
    rows = list(db.scalars(
        select(Message).join(Conversation)
        .where(Conversation.user_id == user.id, Message.role != MessageRole.SYSTEM)
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(40)
    ))
    history = _finalize_history(db, user) + [
        {"role": m.role.value, "content": m.content, "conversation_id": m.conversation_id}
        for m in reversed(rows)
    ]
    return (rows[0].conversation_id if rows else None), history[-60:]


from app.schemas.career_dna_snapshot import SnapshotCreate, SnapshotUpdate
from app.services import career_dna_snapshot as snapshots


def _snapshots(user, db):
    return [{**{column.name: getattr(s, column.name) for column in s.__table__.columns},
             "delta": getattr(s, "_snapshot_delta", None)} for s in snapshots.list_snapshots(user, db)]


@router.get("/snapshots")
def list_snapshots(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return _snapshots(user, db)


@router.post("/snapshots")
def save_snapshot(data: SnapshotCreate, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    snapshots.save_snapshot(user, data, db)
    return _snapshots(user, db)


@router.patch("/snapshots/{snap_id}")
def update_snapshot(snap_id: int, data: SnapshotUpdate, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    try:
        snapshots.update_snapshot(user, snap_id, data, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Snapshot not found") from exc
    return _snapshots(user, db)


@router.delete("/snapshots/{snap_id}")
def delete_snapshot(snap_id: int, user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    try:
        snapshots.delete_snapshot(user, snap_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Snapshot not found") from exc
    return {"deleted": True}
