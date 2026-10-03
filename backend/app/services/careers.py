import re
import asyncio
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.career import Career, CareerMatch
from app.models.roadmap import RoadmapItem
from app.models.user import User
from app.llm import prompts
from app.schemas.career import CareerMatchRequest
from app.services.career_dna import get_dna, get_or_create_dna
from app.services.providers import dna_dict, gemini, memory
from app.services.student_context import career_in_mind_phrase, load_student_context


def search_careers(db: Session, q: str | None = None, category: str | None = None, limit: int = 50) -> list[Career]:
    stmt = select(Career)
    if category:
        stmt = stmt.where(Career.category.ilike(category))
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            Career.title.ilike(needle)
            | Career.category.ilike(needle)
            | Career.summary.ilike(needle)
        )
    return list(db.scalars(stmt.order_by(Career.title).limit(limit)))


def get_career(db: Session, career_id: int | None = None, slug: str | None = None) -> Career | None:
    if slug:
        return db.scalar(select(Career).where(Career.slug == slug))
    if career_id:
        return db.get(Career, career_id)
    return None


def career_detail(db: Session, career: Career, user: User | None = None) -> dict:
    data = {
        "id": career.id,
        "slug": career.slug,
        "title": career.title,
        "category": career.category,
        "emoji": career.emoji,
        "summary": career.summary,
        "description": career.description,
        "what_they_do": career.what_they_do,
        "skills": career.skills or [],
        "subjects": career.subjects or [],
        "degrees": career.degrees or [],
        "industries": career.industries or [],
        "future_paths": career.future_paths or [],
        "salary_range": career.salary_range,
        "outlook": career.outlook,
        "ranking_profile": career.ranking_profile,
        "country_rankings": career.country_rankings or [],
        "fit_rating": None,
        "reasons": None,
    }
    if user:
        match = db.scalar(
            select(CareerMatch).where(
                CareerMatch.user_id == user.id, CareerMatch.career_id == career.id
            )
        )
        if match:
            data["fit_rating"] = round(match.score)
            data["reasons"] = match.reasons or []
    return data


def list_career_matches(db: Session, user: User) -> list[CareerMatch]:
    stmt = (
        select(CareerMatch)
        .where(CareerMatch.user_id == user.id)
        .order_by(CareerMatch.score.desc())
    )
    return list(db.scalars(stmt))


# ---------------------------------------------------------------------------
# Deterministic, explainable career matching engine
# ---------------------------------------------------------------------------

# Each criterion contributes a weighted 0-1 "coverage" ratio to the final
# 0-100 score. Ratios (not raw token counts) keep scores comparable across
# careers with different amounts of text.
MATCH_CRITERIA = (
    ("skills", 0.30),
    ("subjects", 0.25),
    ("interests", 0.20),
    ("career_zones", 0.15),
    ("goals", 0.10),
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _norm(*parts) -> str:
    """Normalize one or more strings into a lowercase searchable key."""
    return " ".join(str(p).lower() for p in parts if p is not None).strip()


def _tokens(text: str) -> set[str]:
    """Significant lowercase tokens (drops 1-letter and pure number tokens)."""
    stop = {"to", "in", "of", "and", "the", "be", "want", "become", "my", "is", "for", "with", "an", "as", "it", "career", "work"}
    return {t for t in _SLUG_RE.split(text.lower()) if len(t) > 1 and not t.isdigit() and t not in stop}


def _career_text(c: Career) -> str:
    """Searchable blob for a career: title + category + everything descriptive."""
    return _norm(
        c.title,
        c.category,
        c.summary,
        c.description,
        c.what_they_do,
        *(c.skills or []),
        *(c.subjects or []),
        *(c.degrees or []),
        *(c.industries or []),
        *(c.future_paths or []),
    )


def _contains(item: str, blob: str) -> bool:
    """True if a student phrase appears in the career blob (full phrase or its
    content words — so 'cloud engineering' also hits careers that mention
    'cloud' or 'engineering' independently)."""
    key = _SLUG_RE.sub(" ", item).strip()
    if not key:
        return False
    if re.search(r"\b" + re.escape(key) + r"\b", blob):
        return True
    it_tokens = _tokens(key)
    if not it_tokens:
        return False
    blob_tokens = _tokens(blob)
    return bool(it_tokens) and it_tokens <= blob_tokens


_REASON_TEMPLATES = {
    "interests": "Your interest in '{0}' shows up in what this career actually does.",
    "skills": "Your skill '{0}' is something this career relies on daily.",
    "subjects": "You study '{0}' — a key academic foundation for this field.",
    "career_zones": "Your career zone '{0}' is exactly where this career sits.",
    "goals": "This career is a direct path toward your goal: '{0}'.",
}


def _overlap_ratio(student_items: list[str] | None, career_blob: str) -> tuple[float, list[str]]:
    """Fraction of the student's items found inside the career text (0->1)."""
    items = [str(i).strip().lower() for i in (student_items or []) if str(i).strip()]
    if not items:
        return 0.0, []
    hits = []
    seen = set()
    for it in items:
        lower = it.lower()
        if _contains(lower, career_blob) and lower not in seen:
            hits.append(lower)
            seen.add(lower)
    return len(hits) / len(items), hits


def _career_matches_excluded(c: Career, excluded: list | None) -> list[str]:
    """Which revoked topics this career is strongly about (title/category first)."""
    if not excluded:
        return []
    title = _norm(c.title, c.category)
    blob = _career_text(c)

    def hits(needle: str, haystack: str) -> bool:
        key = _SLUG_RE.sub(" ", needle).strip()
        if not key:
            return False
        if re.search(r"\b" + re.escape(key) + r"\b", haystack):
            return True
        nt = _tokens(key)
        return bool(nt and nt <= _tokens(haystack))

    suppressed = []
    for phrase in excluded:
        if not str(phrase).strip():
            continue
        # Strong signal: appears in the career's name/category -> hard suppress.
        if hits(phrase, title):
            suppressed.append(phrase)
        # Softer signal: appears deep in the description -> strong discount.
        elif hits(phrase, blob):
            suppressed.append(phrase)
    return suppressed


def _score_career(c: Career, dna) -> tuple[float, list[str]]:
    """Score a single career against the student's DNA.

    Returns (score 0-100, reasons). The score is a weighted average of how
    much of the student's DNA each criterion finds in this career. A sqrt
    curve spreads mid-range results so scores read naturally. Careers tied to
    a topic the student has explicitly ruled out (dna.excluded) are capped so
    they can never win the top spot even if other DNA overlaps.
    """
    blob = _career_text(c)
    covered_weight = 0.0
    weighted = 0.0
    reasons: list[str] = []
    for field, weight in MATCH_CRITERIA:
        items = getattr(dna, field, None) or []
        ratio, hits = _overlap_ratio(items, blob)
        covered_weight += weight
        weighted += weight * ratio
        if hits:
            reasons.append(_REASON_TEMPLATES[field].format(hits[0]))
    ratio = weighted / covered_weight if covered_weight else 0.0
    score = round(100 * (ratio ** 0.7), 1)

    excluded = getattr(dna, "excluded", None) or []
    suppressed = _career_matches_excluded(c, excluded)
    if suppressed:
        for ph in suppressed[:2]:
            topic = str(ph).strip().lower()
            reasons.append(f"You told Novi you're stepping away from {topic or 'this'} — so this career is not in the running.")
        # Hard cap: revoked-topic careers can't beat an honest 30% floor.
        score = 0.0

    return score, reasons[:4]


def _score_catalog(db: Session, dna, ctx: dict | None = None) -> list[dict]:
    """Deterministic scores for every career in the catalog, best first."""
    catalog = search_careers(db, limit=500)
    scored = []
    for c in catalog:
        base, base_reasons = _score_career(c, dna)
        scored.append({"slug": c.slug, "score": base, "reasons": base_reasons})

    # The student's self-declared career is the single strongest signal we have:
    # any catalog career that matches its name/category gets a hard boost so the
    # stated goal can never lose to a vague preference overlap.
    career = " ".join(getattr(dna, "career_zones", None) or [])
    if career:
        want = _tokens(career)
        for item in scored:
            c = next((x for x in catalog if x.slug == item["slug"]), None)
            if not c:
                continue
            both = want & _tokens(_norm(c.title, c.category))
            if want and want <= _tokens(_norm(c.title, c.category)) and not _career_matches_excluded(c, getattr(dna, "excluded", [])):
                item["score"] = min(98.0, item["score"] + 20.0)
                item["reasons"] = (
                    item["reasons"]
                    + [f"You told Novi you have {career} in mind — this career matches that goal."]
                )[:4]

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _store_matches(
    db: Session, user: User, scored: list[dict], limit: int
) -> list[CareerMatch]:
    """Replace the user's stored matches with the top `limit` from `scored`."""
    top = [m for m in scored if m["score"] > 0][:limit]
    for old in list_career_matches(db, user):
        db.delete(old)
    db.commit()

    stored: list[CareerMatch] = []
    for rank, m in enumerate(top, start=1):
        career = db.scalar(select(Career).where(Career.slug == m["slug"]))
        if not career:
            continue
        cm = CareerMatch(
            user_id=user.id,
            career_id=career.id,
            score=float(m["score"]),
            rank=rank,
            reasons=m.get("reasons") or [],
        )
        db.add(cm)
        stored.append(cm)
    db.commit()
    for cm in stored:
        db.refresh(cm)
    return stored


def rescore_matches(db: Session, user: User, limit: int = 1) -> list[CareerMatch]:
    """Recompute the student's stored top match straight from their current DNA.

    Runs after any DNA change (chat refresh, manual edit, auto-extraction) so
    the Careers page always reflects what they believe now — no stale picks.
    """
    dna = get_or_create_dna(user, db)
    ctx = load_student_context(db, user)
    scored = _score_catalog(db, dna, ctx)
    stored = _store_matches(db, user, scored, limit)
    return stored


async def match_careers(db: Session, user: User, request: CareerMatchRequest) -> list[CareerMatch]:
    dna = get_or_create_dna(user, db)
    ctx = load_student_context(db, user)
    scored = _score_catalog(db, dna, ctx)

    # Ranking explanations come directly from matched profile evidence.
    return _store_matches(db, user, scored, request.limit)


# ---------------------------------------------------------------------------
# Career advice (detail page)
# ---------------------------------------------------------------------------

ADVICE_TYPES = {"project", "skill", "explore"}
ADVICE_LINKS = {"passport", "careers", "universities", "roadmap"}

async def career_advice(db: Session, user: User, career: Career) -> dict:
    """Personalized 'why this fits you' + concrete next steps for a career."""

    from app.services import passport as passport_svc

    dna = get_dna(user, db)
    student = {"name": user.display_name, "grade": user.grade, "school": user.school}
    student.update(load_student_context(db, user))
    grade = user.grade or 9

    roadmap_items = [
        {
            "grade": i.grade,
            "stage": i.stage.value,
            "title": i.title,
            "description": i.description,
            "category": i.category,
        }
        for i in db.scalars(
            select(RoadmapItem)
            .where(RoadmapItem.user_id == user.id, RoadmapItem.completed.is_(False), RoadmapItem.grade >= grade)
            .order_by(RoadmapItem.grade, RoadmapItem.order_index)
            .limit(8)
        )
    ]
    passport_counts = {
        c: sum(1 for it in passport_svc.list_items(db, user) if it.category == c)
        for c in passport_svc.CORE_CATEGORIES
    }

    fit_statement, next_steps = None, None
    try:
        result = await asyncio.wait_for(gemini.primary.complete_json(
            prompts.career_advice_prompt(
                {
                    "slug": career.slug, "title": career.title, "category": career.category,
                    "summary": career.summary, "skills": career.skills or [],
                    "subjects": career.subjects or [], "industries": career.industries or [],
                },
                dna_dict(dna), student, roadmap_items, passport_counts,
            ),
            system=prompts.CAREER_ADVICE_SYSTEM,
        ), timeout=75)
        if isinstance(result, dict):
            fit_statement = str(result.get("fit_statement") or "").strip() or None
            next_steps = _clean_steps(result.get("next_steps"))
    except Exception as exc:
        raise ValueError("Gemini advice is unavailable. The Gemini API may have reached its request quota. Check its quota or retry when capacity is available.") from exc

    if not next_steps or not fit_statement:
        raise ValueError("Gemini returned incomplete advice. Please retry.")

    match = db.scalar(
        select(CareerMatch).where(
            CareerMatch.user_id == user.id, CareerMatch.career_id == career.id
        )
    )
    result = {
        "career_slug": career.slug,
        "fit_rating": round(match.score) if match else None,
        "reasons": (match.reasons or []) if match else None,
        "fit_statement": fit_statement,
        "next_steps": next_steps[:3],
    }
    return result


def _clean_steps(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    out = []
    for s in value:
        if not isinstance(s, dict):
            continue
        step_type = str(s.get("type") or "").strip()
        title = str(s.get("title") or "").strip()
        why = str(s.get("why") or "").strip()
        link = str(s.get("link") or "").strip()
        if step_type not in ADVICE_TYPES or link not in ADVICE_LINKS or not title or not why:
            continue
        out.append({"type": step_type, "title": title, "why": why, "link": link})
    return out[:3]


def _heuristic_advice(career: Career, dna, roadmap_items: list[dict]) -> tuple[str, list[dict]]:
    d = dna_dict(dna)
    interests = (d.get("interests") or [])[:2]
    strengths = (d.get("strengths") or [])[:2]
    if interests and strengths:
        fit = (
            f"With your interest in {interests[0]} and your strength in {strengths[0]}, "
            f"{career.title} could be a natural place to put what you're good at to work. "
            "It asks for real effort, but it's the kind of path you can grow into."
        )
    elif interests:
        fit = (
            f"I've noticed you gravitate toward {interests[0]}. {career.title} blends that "
            "with real-world problems — worth exploring before you decide."
        )
    else:
        fit = (
            f"{career.title} isn't about having the world figured out. It's about combining "
            "curiosity and consistent practice — let's figure out if it fits you."
        )

    if roadmap_items:
        steps = [
            {
                "type": "explore",
                "title": f"Next on your roadmap: {it['title']}",
                "why": "It's already a step on your plan toward your goal.",
                "link": "roadmap",
            }
            for it in roadmap_items[:3]
        ]
    else:
        steps = [
            {
                "type": "project",
                "title": f"Build a small {career.title.lower()} project",
                "why": "The fastest way to test whether a path fits is to try doing it.",
                "link": "passport",
            },
            {
                "type": "skill",
                "title": f"Learn {(career.skills or ['a core skill'])[0]}",
                "why": "This is one of the core skills this career rewards.",
                "link": "roadmap",
            },
            {
                "type": "explore",
                "title": "Explore university programs in this field",
                "why": "See where this career can take you after school.",
                "link": "universities",
            },
        ]
    return fit, steps
