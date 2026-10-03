from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.career import CareerAdviceOut, CareerDetailOut, CareerMatchOut, CareerMatchRequest, CareerOut
from app.services import careers as career_service

router = APIRouter(prefix="/careers", tags=["careers"])


@router.get("", response_model=list[CareerOut])
async def list_careers(
    q: str | None = None,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return career_service.search_careers(db, q=q, category=category, limit=limit)


@router.get("/categories")
async def categories(db: Session = Depends(get_db)):
    """Categories ordered by how many careers sit in them, so the client's
    top-filter row can just take the first few. Counts are aggregated across
    raw category spellings before normalising, otherwise the ordering splits
    on aliases. Ties fall back to alphabetical for a stable response."""
    from sqlalchemy import select, func
    from app.db.career_catalog import normalize_category
    from app.models.career import Career

    counts: dict[str, int] = {}
    for cat, n in db.execute(select(Career.category, func.count()).group_by(Career.category)):
        label = normalize_category(cat)
        counts[label] = counts.get(label, 0) + n
    return sorted(counts, key=lambda c: (-counts[c], c.lower()))


@router.get("/matches", response_model=list[CareerMatchOut])
async def my_matches(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    matches = career_service.list_career_matches(db, user)
    return [CareerMatchOut.model_validate(m) for m in matches]


@router.post("/match", response_model=list[CareerMatchOut])
async def match_careers(
    request: CareerMatchRequest,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    matches = await career_service.match_careers(db, user, request)
    return [CareerMatchOut.model_validate(m) for m in matches]


@router.get("/{slug}/advice", response_model=CareerAdviceOut)
async def career_advice(
    slug: str,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    career = career_service.get_career(db, slug=slug)
    if not career:
        raise HTTPException(status_code=404, detail="Career not found")
    try:
        return await career_service.career_advice(db, user, career)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{slug}", response_model=CareerDetailOut)
async def career_detail(
    slug: str,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    career = career_service.get_career(db, slug=slug)
    if not career:
        raise HTTPException(status_code=404, detail="Career not found")
    return career_service.career_detail(db, career, user=user)