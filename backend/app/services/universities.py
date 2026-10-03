import asyncio
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.university import University, UniversityMatch
from app.models.user import User
from app.llm import prompts
from app.schemas.university import ReadinessRequest, UniversityFilters
from app.services.career_dna import get_dna
from app.services.providers import dna_dict, gemini, memory
from app.services.student_context import (
    career_in_mind_phrase,
    load_student_context,
    norm_country,
)


def search_universities(db: Session, filters: UniversityFilters) -> list[University]:
    stmt = select(University)
    if filters.q:
        needle = f"%{filters.q.lower()}%"
        stmt = stmt.where(
            University.name.ilike(needle)
            | University.course.ilike(needle)
            | University.country.ilike(needle)
            | University.about.ilike(needle)
        )
    if filters.country:
        stmt = stmt.where(University.country == filters.country)
    if filters.course:
        stmt = stmt.where(
            University.course.ilike(f"%{filters.course.strip()}%")
            | University.courses.contains(filters.course.strip())
        )
    if filters.entry_query:
        stmt = stmt.where(University.entry_requirements.ilike(f"%{filters.entry_query.strip()}%"))
    if filters.subject:
        subject = filters.subject.strip().lower()
        stmt = stmt.where(
            (University.subject == subject)
            | University.courses.contains([subject])
        )
    if filters.university_type:
        stmt = stmt.where(University.university_type == filters.university_type)
    if filters.min_rank:
        stmt = stmt.where(University.ranking <= filters.min_rank)
    if filters.max_fees is not None:
        stmt = stmt.where(University.fees_per_year <= filters.max_fees)
    if filters.scholarships is not None:
        stmt = stmt.where(University.scholarships == filters.scholarships)
    # Authoritative ordering: without a subject filter, a bare "best rank" is
    # meaningless (a school can be #1 in one subject and far down in another),
    # so default to an alphabetical listing. With a subject filter, order by
    # that subject's rank. Ranked universities always sort above unranked ones
    # (MySQL sorts NULLs first on ASC, which would show unranked schools on top).
    if filters.subject:
        stmt = stmt.order_by(
            University.ranking.is_(None),
            University.ranking.asc(),
            University.name.asc(),
        ).limit(min(filters.limit, 200))
        results = list(db.scalars(stmt))
        def sort_key(u: University):
            ranks = u.rankings or {}
            if filters.subject in ranks:
                return (0, ranks[filters.subject], u.name.lower())
            if u.ranking is not None:
                return (1, u.ranking, u.name.lower())
            return (2, 10**6, u.name.lower())
        results.sort(key=sort_key)
        return results[: filters.limit]
    stmt = stmt.order_by(University.name.asc()).limit(min(filters.limit, 200))
    return list(db.scalars(stmt))[: filters.limit]


def get_university(db: Session, university_id: int | None = None, slug: str | None = None) -> University | None:
    if slug:
        return db.scalar(select(University).where(University.slug == slug))
    if university_id:
        return db.get(University, university_id)
    return None


def list_countries(db: Session) -> list[str]:
    rows = db.scalars(select(University.country).distinct().order_by(University.country))
    return [r for r in rows if r]


SUBJECT_ORDER = [
    "computer-science", "data-science", "engineering", "architecture", "medicine",
    "law", "business", "economics", "science", "arts",
]
SUBJECT_LABELS = {
    "computer-science": "Computer Science",
    "data-science": "Data Science & AI",
    "engineering": "Engineering",
    "architecture": "Architecture",
    "medicine": "Medicine & Health",
    "law": "Law",
    "business": "Business & Management",
    "economics": "Economics & Policy",
    "science": "Sciences",
    "arts": "Arts & Humanities",
}


def list_subjects(db: Session) -> list[str]:
    seen = set()
    for u in db.scalars(select(University.rankings)):
        if u:
            seen.update(k for k in u if k in SUBJECT_ORDER)
    if not seen:
        rows = db.scalars(select(University.subject).distinct())
        seen = {r for r in rows if r in SUBJECT_ORDER}
    return [s for s in SUBJECT_ORDER if s in seen]


async def readiness(db: Session, user: User, request: ReadinessRequest) -> UniversityMatch:
    university = db.get(University, request.university_id)
    if not university:
        raise ValueError("University not found")

    dna = get_dna(user, db)
    profile = _profile_summary(db, user)
    student = {"name": user.display_name, "grade": user.grade, "school": user.school}
    student.update(load_student_context(db, user))

    assessment = None
    try:
        result = await gemini.complete_json(
            prompts.university_readiness_prompt(
                {
                    "name": university.name,
                    "rank": university.ranking,
                    "fees": university.fees_per_year,
                    "type": university.university_type,
                    "course": request.course or university.course,
                    "entry_requirements": university.entry_requirements,
                    "strengths": university.strengths or [],
                    "about": university.about,
                },
                dna_dict(dna),
                profile,
                student,
            ),
            system=prompts.UNIVERSITY_READINESS_SYSTEM,
        )
        if isinstance(result, dict):
            assessment = result
    except Exception as exc:
        print(f"[universities] readiness LLM failed, using heuristic: {exc}")

    if assessment is None:
        assessment = _heuristic_readiness(user, university, dna)

    existing = db.scalar(
        select(UniversityMatch).where(
            UniversityMatch.user_id == user.id,
            UniversityMatch.university_id == university.id,
        )
    )
    if existing is None:
        existing = UniversityMatch(user_id=user.id, university_id=university.id)
        db.add(existing)
    existing.course = request.course or university.course
    existing.readiness = max(0, min(100, float(assessment.get("readiness", 50))))
    existing.strengths = assessment.get("strengths") or []
    existing.improvements = assessment.get("improvements") or []
    existing.next_steps = assessment.get("next_steps") or []
    db.commit()
    db.refresh(existing)
    memory.archive(
        user,
        f"User checked university readiness for {university.name} "
        f"({existing.course}): {existing.readiness}%.",
        ("university", "readiness"),
    )
    return existing


def recent_matches(db: Session, user: User) -> list[UniversityMatch]:
    stmt = (
        select(UniversityMatch)
        .where(UniversityMatch.user_id == user.id)
        .order_by(UniversityMatch.readiness.desc())
    )
    return list(db.scalars(stmt))


def recommend(db: Session, user: User, limit: int = 6) -> list[dict]:
    """Context-grounded university recommendations — rank programs by how well they
    align with the student's Career DNA **plus** the onboarding context they gave
    (target country, dreamed-of universities, enjoyed subjects, a career in mind).
    Deterministic and fast (no LLM). Falls back to recent readiness checks when the
    DNA is not filled."""
    dna = get_dna(user, db)
    ctx = load_student_context(db, user)
    buckets: dict[str, list[str]] = {
        "career_zones": (dna.career_zones or []) if dna else [],
        "interests": (dna.interests or []) if dna else [],
        "subjects": (dna.subjects or []) if dna else [],
        "goals": (dna.goals or []) if dna else [],
        "skills": (dna.skills or []) if dna else [],
    }
    weights = {"career_zones": 4, "goals": 3, "interests": 3, "subjects": 2, "skills": 1}
    phrases = [p for arr in buckets.values() for p in arr if p and len(p.strip()) > 1]
    has_context = any(
        (ctx.get("country_preference"), ctx.get("study_destination"),
         ctx.get("dream_universities"), ctx.get("subjects_enjoyed"), career_in_mind_phrase(ctx))
    )
    if not phrases and not has_context:
        return recent_matches(db, user)

    dest_key = (ctx.get("country_preference") or "").strip()
    dream = (ctx.get("dream_universities") or "").strip().lower()
    career = " ".join((dna.career_zones or []) if dna else [])
    career_toks = _tok(career) if career else set()
    subjects_ctx = [str(s).strip().lower() for s in ((dna.subjects or []) if dna else []) if str(s).strip()]

    catalog = list(db.scalars(select(University).order_by(University.ranking.asc())))
    scored: list[dict] = []
    for uni in catalog:
        hay = " ".join(
            [uni.course or "", uni.subject or "", " ".join(uni.courses or []), " ".join(uni.strengths or []), uni.about or ""]
        ).lower()
        hay_toks = _tok(hay)
        alignment = 0
        best_field, best_phrase = None, None
        for field, arr in buckets.items():
            for phrase in arr:
                p = phrase.lower()
                from app.services.careers import _contains
                if _contains(p, hay):
                    alignment += weights[field]
                    if best_field is None or weights[field] > weights.get(best_field, 0):
                        best_field, best_phrase = field, phrase
        reasons_extra: list[str] = []
        dream_hit = False

        if dest_key and norm_country(uni.country) == dest_key:
            alignment += 8
            reasons_extra.append(
                f"You told Novi you want to study in {ctx['study_destination']} — this is in your target country."
            )
        for subject in subjects_ctx:
            match = subject in hay or subject.rstrip("s") in hay or any(
                w.startswith(subject.rstrip("s")) for w in hay.split()
            )
            if match:
                alignment += 3
                reasons_extra.append(f"{subject.title()} is one of the subjects you enjoy.")
                break
        if career_toks and career_toks <= hay_toks:
            alignment += 6
            reasons_extra.append(f"Programs here connect to {career}, which you have in mind.")
        if dream and uni.name.lower() in dream:
            alignment += 30
            dream_hit = True
            reasons_extra.insert(0, f"You mentioned {uni.name} yourself — it's at the top of your list.")

        if alignment == 0:
            continue
        readiness = _heuristic_readiness(user, uni, dna)["readiness"]
        aligned = min(18, alignment * 2)
        if dream_hit:
            aligned = max(aligned, 25)
        readiness = min(98, readiness + aligned)
        base_reason = _reason(best_field, best_phrase)
        scored.append(
            {
                "id": uni.id,
                "readiness": readiness,
                "strengths": [uni.subject or "Subject strength", "Relevant coursework"],
                "improvements": ["Research depth", "Extracurricular profile"],
                "next_steps": [
                    f"Build a project or case study related to {best_phrase or uni.subject}",
                    "Strengthen grades in your core subjects",
                    "Explore scholarship and application timelines",
                ],
                "university": uni,
                "reason": " ".join(reasons_extra) + " " + base_reason if reasons_extra else base_reason,
            }
        )
    scored.sort(key=lambda m: m["readiness"], reverse=True)
    return scored[:limit]


def _reason(field: str | None, phrase: str | None) -> str:
    labels = {
        "career_zones": "a top career zone in your DNA",
        "goals": "one of your stated career goals",
        "interests": "an area you're actively interested in",
        "subjects": "one of your favourite subjects",
        "skills": "a skill you're building",
    }
    if field and phrase:
        return f"Coursework aligned with {phrase.lower()} — {labels.get(field, 'your profile')}."
    return "Program broadly aligned with your profile."


def _tok(text: str | None) -> set[str]:
    """Significant lowercase tokens for phrase-matching (drops 1-letter words)."""
    if not text:
        return set()
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 1 and not t.isdigit()}


def average_readiness(db: Session, user: User) -> int:
    matches = recent_matches(db, user)
    if not matches:
        return 0
    return round(sum(m.readiness for m in matches) / len(matches))


def _profile_summary(db: Session, user: User) -> dict:
    from app.models.checkin import WeeklyCheckin
    from app.models.passport import PassportItem
    from app.models.roadmap import Goal, RoadmapItem

    goals = list(db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.status == "active")))
    passport = list(db.scalars(select(PassportItem).where(PassportItem.user_id == user.id)))
    roadmap = list(db.scalars(select(RoadmapItem).where(RoadmapItem.user_id == user.id)))
    checkins = list(
        db.scalars(
            select(WeeklyCheckin)
            .where(WeeklyCheckin.user_id == user.id)
            .order_by(WeeklyCheckin.week_start.desc())
            .limit(3)
        )
    )
    return {
        "grade": user.grade,
        "school": user.school,
        "goals": [{"title": g.title, "category": g.category.value} for g in goals],
        "passport": [{"category": p.category.value, "title": p.title} for p in passport],
        "roadmap_completed": sum(1 for r in roadmap if r.completed),
        "roadmap_total": len(roadmap),
        "recent_checkins": [
            {"accomplishments": c.accomplishments, "learnings": c.learnings} for c in checkins
        ],
    }


def _heuristic_readiness(user: User, university: University, dna) -> dict:
    grade = user.grade or 9
    base = grade * 5  # 45 -> 60
    alignment = 0
    if dna and (dna.interests or dna.subjects):
        blob = " ".join((dna.interests or []) + (dna.subjects or [])).lower()
        if university.subject.lower() in blob:
            alignment = 15
        elif any(t.lower() in university.about.lower() for t in (dna.interests or [])):
            alignment = 10
    rank_bonus = 10 if (university.ranking or 500) <= 50 else 0
    readiness = min(95, base + alignment + rank_bonus)
    return {
        "readiness": readiness,
        "strengths": ["Academic performance", university.subject or "Subject interest"],
        "improvements": ["Research depth", "Leadership", "Extracurricular profile"],
        "next_steps": [
            "Strengthen your grades in key subjects",
            f"Explore a project related to {university.subject or 'your subject of interest'}",
            "Join an activity that shows leadership or initiative",
        ],
    }


async def advice(
    db: Session,
    user: User,
    question: str,
    subject: str | None = None,
    university_ids: list[int] | None = None,
) -> dict:
    """Return a personalized, web-grounded "which university is best" answer."""
    dna = get_dna(user, db)
    student = {"name": user.display_name, "grade": user.grade, "school": user.school}
    student.update(load_student_context(db, user))

    if university_ids:
        stmt = select(University).where(University.id.in_(university_ids)).limit(10)
        candidates = list(db.scalars(stmt))
    elif subject:
        filters = UniversityFilters(subject=subject, limit=5)
        candidates = search_universities(db, filters)
    else:
        candidates = recommend(db, user, limit=5)
        candidates = [m["university"] for m in candidates]
        if not candidates:
            filters = UniversityFilters(limit=5)
            candidates = search_universities(db, filters)

    profile = [c for c in candidates if c][:5]
    payload = [
        {
            "id": u.id,
            "name": u.name,
            "country": u.country,
            "city": u.city,
            "course": u.course,
            "subject": u.subject,
            "ranking": u.ranking,
            "fees_per_year": u.fees_per_year,
            "university_type": u.university_type,
            "about": (u.about or "")[:400],
        }
        for u in profile
    ]

    fallback = _advice_fallback(question, profile, dna)

    try:
        result = await asyncio.wait_for(gemini.primary.complete_grounded(
            prompts.university_advice_prompt(question, payload, dna_dict(dna), student),
            system=prompts.UNIVERSITY_ADVICE_SYSTEM,
        ), timeout=75)
        answer = (result.get("text") or "").strip()
        if not answer:
            raise ValueError("empty answer")
        sources = result.get("sources") or []
    except Exception as exc:
        raise ValueError("Gemini university advice is unavailable. The Gemini API may have reached its request quota. Check its quota or retry when capacity is available.") from exc

    memory.archive(
        user,
        f"User asked Novi for university advice: \"{question}\" → {profile[0].name if profile else 'none'}.",
        ("university", "advice"),
    )
    return {"answer": answer, "sources": sources, "candidates": profile}


def _advice_fallback(question: str, candidates: list, dna) -> str:
    target = None
    if dna and (dna.interests or dna.subjects or dna.career_zones):
        blob = " ".join(
            (dna.interests or []) + (dna.subjects or []) + (dna.career_zones or [])
        ).lower()
        for u in candidates:
            hay = " ".join([u.course or "", u.subject or ""]).lower()
            if any(b in hay for b in blob.split() if len(b) > 3):
                target = u
                break

    ranked = [u for u in candidates if u.ranking is not None]
    best = target or (min(ranked, key=lambda u: u.ranking) if ranked else (candidates[0] if candidates else None))
    if not best:
        return (
            "I don't have enough data yet to recommend a specific university. "
            "Could you tell me about your subjects and career interests first? 🎓"
        )
    place = f"{best.city}, {best.country}" if best.city else best.country
    rank_clause = ""
    if best.ranking is not None:
        rank_clause = f" ranked #{best.ranking} in its subject"
    fee_clause = ""
    if best.fees_per_year:
        fee_clause = f" with yearly fees around ${best.fees_per_year:,}"
    return (
        f"Based on your profile, I'd look most closely at {best.name} in {place}{rank_clause}"
        f"{fee_clause}.\n\nIt lines up with the fields you care about ({(best.subject or 'your interests').replace('-', ' ')}), "
        f"and it's a realistic target to aim for. Want me to check your readiness for it, "
        f"or compare two schools side by side? 🎓"
    )
