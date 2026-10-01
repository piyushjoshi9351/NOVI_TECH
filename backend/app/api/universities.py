from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.models.user import User
from app.schemas.university import (
    AdviceOut,
    AdviceRequest,
    ReadinessRequest,
    UniversityFilters,
    UniversityMatchOut,
    UniversityOut,
)
from app.services import universities as uni_service

router = APIRouter(prefix="/universities", tags=["universities"])


def _university_payload(university, course_query: str | None = None) -> dict:
    data = {
        "id": university.id,
        "slug": university.slug,
        "name": university.name,
        "country": university.country,
        "city": university.city,
        "course": university.course,
        "subject": university.subject,
        "ranking": university.ranking,
        "fees_per_year": university.fees_per_year,
        "university_type": university.university_type,
        "scholarships": university.scholarships,
        "entry_requirements": university.entry_requirements,
        "about": university.about,
        "website": university.website,
        "tags": university.tags,
        "strengths": university.strengths,
        "courses": university.courses,
        "rankings": university.rankings,
    }
    if course_query:
        needle = course_query.strip().lower()
        courses = [university.course] + (university.courses or [])
        matched = next((c for c in courses if c and needle in c.lower()), None)
        if matched:
            data["course"] = matched
    return data


@router.get("", response_model=list[UniversityOut])
async def universities(
    q: str | None = None,
    course: str | None = None,
    entry_query: str | None = None,
    country: str | None = None,
    subject: str | None = None,
    min_rank: int | None = None,
    max_fees: int | None = None,
    university_type: str | None = None,
    scholarships: bool | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
):
    filters = UniversityFilters(
        q=q,
        course=course,
        entry_query=entry_query,
        country=country,
        subject=subject,
        min_rank=min_rank,
        max_fees=max_fees,
        university_type=university_type,
        scholarships=scholarships,
        limit=limit,
    )
    return [_university_payload(u, course_query=course) for u in uni_service.search_universities(db, filters)]


@router.get("/filters")
async def filters(db: Session = Depends(get_db)):
    from sqlalchemy import select
    from app.models.university import University

    subjects = uni_service.list_subjects(db)
    universities = list(db.scalars(select(University)))
    courses = sorted({course for u in universities for course in ([u.course] + (u.courses or [])) if course})
    types = sorted({u.university_type for u in universities if u.university_type})
    ranks = [u.ranking for u in universities if u.ranking is not None]
    fees = [u.fees_per_year for u in universities if u.fees_per_year is not None]
    return {
        "countries": uni_service.list_countries(db),
        "subjects": subjects,
        "subject_labels": {s: uni_service.SUBJECT_LABELS.get(s, s) for s in subjects},
        "courses": courses,
        "university_types": types,
        "bounds": {"ranking": {"max": max(ranks, default=100)}, "fees": {"max": max(fees, default=50000)}},
    }


@router.get("/recommended", response_model=list[UniversityMatchOut])
async def recommended(user: User = Depends(get_current_student), db: Session = Depends(get_db)):
    return uni_service.recommend(db, user)


@router.post("/readiness", response_model=UniversityMatchOut)
async def readiness(
    request: ReadinessRequest,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    try:
        result = await uni_service.readiness(db, user, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/advice", response_model=AdviceOut)
async def advice(
    request: AdviceRequest,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    try:
        return await uni_service.advice(
            db, user, request.question, subject=request.subject, university_ids=request.university_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc



@router.get("/{slug}", response_model=UniversityOut)
async def university_detail(slug: str, db: Session = Depends(get_db)):
    university = uni_service.get_university(db, slug=slug)
    if not university:
        raise HTTPException(status_code=404, detail="University not found")
    return university
