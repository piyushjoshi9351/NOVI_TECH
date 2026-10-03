"""Parent-safe projection of a student's data, gated by consent sections.

This module is the ONLY place that decides what a parent may see. Everything it
returns is copied field-by-field into the allowlist schemas in
``app/schemas/parent.py`` -- no ORM object is ever serialized directly, so a new
column on ``users``/``career_dna`` cannot leak in by default.

Hard exclusions (never read here, at any consent level)
------------------------------------------------------
* conversations / messages -- no chat, ever
* Letta: archival passages, core-memory blocks, ``novistate`` (no call to Letta
  exists in this module at all)
* ``career_dna.sources`` / ``excluded`` / ``novi_reflection`` (verbatim quotes)
* WeeklyCheckin free text: accomplishments, challenges, pride, next_week, notes,
  mood, energy
* tasks, weekly priorities, planner blocks (day-to-day activity)
* passport achievement *titles* (counts only -- a title is often student prose)
* the student's email, password hash, agent id, and internal row ids

Consent
-------
Section gating happens HERE, not as a 403 at the edge. ``basic``/``insights``/
``memory`` map to the stored consent on the link; an unshared section comes back
as ``None`` so the UI can render "<First name> hasn't shared this" without a
failed request. Revoking a section therefore removes its data from the very next
response.

Because the same ``consented`` view feeds the insight cache key, revoking a
section also invalidates any insight derived from it.

Deterministic formulas (documented in PARENT_DASHBOARD.md)
----------------------------------------------------------
``profile_strength``
    Weighted blend, capped at 100:
    ``0.30*dna_pct + 0.25*top_match_score + 0.15*goal_momentum
    + 0.10*roadmap_pct + 0.10*passport_score + 0.10*onboarding``
    where ``dna_pct`` is 100 when the DNA is filled else 15 per populated field
    (traits/interests/strengths/career_zones, max 4), ``goal_momentum`` is 20 per
    active goal (max 100), ``onboarding`` is 100 once onboarding is complete.
    Reuses the existing student-dashboard components from
    ``app.services.dashboard`` so parent and student numbers agree.

``university_readiness``
    Mean ``readiness`` across the student's ranked university matches, capped at
    ``READINESS_SAMPLE``. ``None`` when there are no matches -- never 0, because
    "no data" must not read as "no readiness".

``journey.stage_label``
    Friendly label for the grade band (see ``STAGE_LABELS``). ``None`` when the
    grade is unknown or outside 9-12.
"""

import logging
from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.career_dna import CareerDNA
from app.models.enums import GoalStatus, PassportCategory
from app.models.growth import GraphSnapshot, GrowthMilestone
from app.models.passport import PassportItem
from app.models.roadmap import Goal, RoadmapItem
from app.models.user import User
from app.schemas.parent import (
    BasicOverview,
    DnaSnapshotThemes,
    GrowthHistory,
    GrowthMilestoneOut,
    GrowthTrendPoint,
    InsightsResponse,
    ParentPassportItem,
    JourneyProgress,
    OverviewGoal,
    OverviewResponse,
    ParentStudentRef,
    PassportCounts,
)

logger = logging.getLogger("novi.parent_projection")

MAX_GOALS = 5
MAX_THEMES = 3
MAX_FOCUS = 4
MAX_INTERESTS = 6
MAX_MATCHES = 5
MAX_MILESTONES = 10
MAX_PASSPORT_ITEMS = 40
TREND_DAYS = 90

# university_matches averaged for university_readiness.
READINESS_SAMPLE = 5

MAX_DNA_THEMES = 3

# Grade band -> friendly label. Anything outside 9-12 gets None (rendered as "—"),
# never a guessed stage.
STAGE_LABELS: dict[int, str] = {
    9: "Discover your interests",
    10: "Explore & Experiment",
    11: "Build your direction",
    12: "Get ready for what's next",
}

# Read by the insight + advisor layers. NEVER add raw text here.
SNAPSHOT_SECTIONS = ("basic", "insights", "memory")


def stage_label(grade: int | None) -> str | None:
    if grade is None:
        return None
    return STAGE_LABELS.get(int(grade))


def student_ref(student: User) -> ParentStudentRef:
    """Identity only: first name + grade. Never the last name, email or agent id."""
    return ParentStudentRef(first_name=student.first_name or "", grade=student.grade)


# --------------------------------------------------------------------------- components
def _dna_pct(dna: CareerDNA | None) -> int:
    """0-100 richness of the DNA's own summary fields. Never reads sources."""
    if dna is None:
        return 0
    if getattr(dna, "dna_filled", False):
        return 100
    populated = sum(
        1 for f in (dna.traits, dna.interests, dna.strengths, dna.career_zones) if f
    )
    return min(100, populated * 15)


def _goal_momentum(active_goals: int) -> int:
    return min(100, active_goals * 20)


def profile_strength(
    *,
    dna: CareerDNA | None,
    top_match_score: float,
    active_goals: int,
    roadmap_percent: int,
    passport_score: int,
    onboarding_complete: bool,
) -> int | None:
    """Weighted blend of the student's own progress signals, capped at 100.

    See the module docstring for the weights. Every input is a count or a
    bounded score -- no free text, so the value cannot leak content.

    Returns **None**, not 0, when the student has genuinely no data yet: a
    "0% profile strength" badge would read as a judgement about the child when
    it actually just means we know nothing. Completing onboarding counts as real
    signal, so it does produce a number.
    """
    value = (
        0.30 * _dna_pct(dna)
        + 0.25 * max(0.0, min(100.0, top_match_score))
        + 0.15 * _goal_momentum(active_goals)
        + 0.10 * max(0, min(100, roadmap_percent))
        + 0.10 * max(0, min(100, passport_score))
        + 0.10 * (100 if onboarding_complete else 0)
    )
    if value <= 0:
        return None
    return int(round(min(100, max(0, value))))


def _roadmap_percent(db: Session, student_id: int) -> int | None:
    """Percent of roadmap steps completed, or None when there is no roadmap."""
    total, done = db.execute(
        select(
            func.count(RoadmapItem.id),
            func.coalesce(_sum_if(RoadmapItem.completed), 0),
        ).where(RoadmapItem.user_id == student_id)
    ).one()
    if not total:
        return None
    return int(round(100 * done / total))


def _sum_if(column):
    """`SUM(CASE WHEN <column> THEN 1 ELSE 0 END)` -- the portable conditional sum.

    Deliberately NOT ``func.iif``: that emits MySQL's ``iif()``, which exists in
    SQLite (so the test suite passes) but NOT in Oracle MySQL 8, where it raises
    "FUNCTION novi_db.iif does not exist". Only a real-DB smoke test catches this,
    which is why there is one.
    """
    return func.sum(case((column.is_(True), 1), else_=0))


def _passport_counts(db: Session, student_id: int) -> PassportCounts:
    """Passport counts per category in ONE aggregate query.

    Categories with a zero count are omitted so an empty passport reads as
    empty rather than as a grid of zeros. ``verified`` counts only the
    student-verified items.
    """
    total, verified = db.execute(
        select(
            func.count(PassportItem.id),
            func.coalesce(_sum_if(PassportItem.verified), 0),
        ).where(PassportItem.user_id == student_id)
    ).one()

    rows = db.execute(
        select(PassportItem.category, func.count(PassportItem.id))
        .where(PassportItem.user_id == student_id)
        .group_by(PassportItem.category)
    ).all()

    by_category: dict[str, int] = {}
    for category, count in rows:
        if not count:
            continue
        key = getattr(category, "value", category)
        by_category[str(key)] = int(count)
    return PassportCounts(by_category=by_category, total=int(total or 0), verified=int(verified or 0))


def _passport_items(db: Session, student_id: int) -> list[ParentPassportItem]:
    """The passport entries themselves, for the ``insights`` scope only.

    This is deliberately NOT part of ``build_basic``. ``basic`` is irrevocable
    (``locked: true`` in the consent UI), so exposing student-authored free text
    there would be permanent and un-consentable. Under ``insights`` the student
    can revoke it, and revocation removes these entries immediately.

    Ordering is newest-first by ``date_achieved`` then ``created_at`` so the most
    recent achievement leads, matching how a student reads their own passport.
    """
    rows = db.execute(
        select(PassportItem)
        .where(PassportItem.user_id == student_id)
        .order_by(
            PassportItem.date_achieved.is_(None),
            PassportItem.date_achieved.desc(),
            PassportItem.created_at.desc(),
            PassportItem.id.desc(),
        )
        .limit(MAX_PASSPORT_ITEMS)
    ).scalars().all()

    return [
        ParentPassportItem(
            id=item.id,
            category=str(getattr(item.category, "value", item.category)),
            title=item.title,
            description=item.description or "",
            skills=[str(s) for s in (item.skills or [])],
            date_achieved=item.date_achieved,
            certificate_url=item.certificate_url,
            verified=bool(item.verified),
        )
        for item in rows
    ]


def _university_readiness(db: Session, student_id: int) -> int | None:
    """Mean readiness across the top ranked university matches, else None.

    ``university_matches`` has no rank column, so "top" = highest readiness.
    """
    from app.models.university import UniversityMatch

    rows = db.execute(
        select(UniversityMatch.readiness)
        .where(UniversityMatch.user_id == student_id)
        .order_by(UniversityMatch.readiness.desc())
        .limit(READINESS_SAMPLE)
    ).scalars().all()
    values = [float(r) for r in rows if r is not None]
    if not values:
        return None
    return int(round(sum(values) / len(values)))


def _dna_themes(dna: CareerDNA | None) -> list[str]:
    """Top themes from career_zones, then interests, then strengths.

    Labels only. ``sources``/``excluded`` are never touched.
    """
    if dna is None:
        return []
    seen: set[str] = set()
    themes: list[str] = []
    for bucket in (dna.career_zones, dna.interests, dna.strengths):
        for value in bucket or []:
            label = str(value).strip()
            key = label.lower()
            if not label or key in seen:
                continue
            seen.add(key)
            themes.append(label)
            if len(themes) >= MAX_DNA_THEMES:
                return themes
    return themes


def _career_direction(db: Session, student: User) -> str | None:
    """Top career match category -> first DNA career zone -> onboarding answer."""
    from app.models.career import Career, CareerMatch

    row = db.execute(
        select(Career.category)
        .join(CareerMatch, CareerMatch.career_id == Career.id)
        .where(CareerMatch.user_id == student.id)
        .order_by(CareerMatch.rank.asc(), CareerMatch.score.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row:
        return str(row) or None

    dna = db.scalar(select(CareerDNA).where(CareerDNA.user_id == student.id))
    if dna and dna.career_zones:
        return str(dna.career_zones[0])

    # Last resort: what the student typed during onboarding.
    try:
        from app.services.student_context import load_student_context

        ctx = load_student_context(db, student)
        answer = ctx.get("career_in_mind") or ctx.get("career_in_mind_phrase")
        if answer:
            return str(answer)
    except Exception:  # never let an optional context break the dashboard
        logger.debug("onboarding career answer unavailable for student %s", student.id)
    return None


def _active_goals(db: Session, student_id: int) -> list[Goal]:
    return list(
        db.scalars(
            select(Goal)
            .where(Goal.user_id == student_id, Goal.status == GoalStatus.ACTIVE)
            .order_by(Goal.id.asc())
            .limit(MAX_GOALS)
        )
    )


# --------------------------------------------------------------------------- sections
def build_basic(db: Session, student: User) -> BasicOverview:
    """The ``basic`` consent section."""
    from app.services.passport import completion as passport_completion
    from app.services.careers import list_career_matches

    dna = db.scalar(select(CareerDNA).where(CareerDNA.user_id == student.id))

    goals = _active_goals(db, student.id)
    roadmap_percent = _roadmap_percent(db, student.id)
    passport = _passport_counts(db, student.id)

    matches = list_career_matches(db, student)
    top_score = float(matches[0].score) if matches else 0.0

    completion = passport_completion(db, student)
    passport_score = int(completion.get("score", 0)) if isinstance(completion, dict) else 0
    onboarding_complete = student.onboarding_completed_at is not None

    themes = _dna_themes(dna)

    return BasicOverview(
        school=student.school or None,
        career_direction=_career_direction(db, student),
        profile_strength=profile_strength(
            dna=dna,
            top_match_score=top_score,
            active_goals=len(goals),
            roadmap_percent=roadmap_percent or 0,
            passport_score=passport_score,
            onboarding_complete=onboarding_complete,
        ),
        university_readiness=_university_readiness(db, student.id),
        dna_snapshot=DnaSnapshotThemes(themes=themes) if themes else None,
        goals=[
            OverviewGoal(
                id=g.id,
                title=g.title,
                category=getattr(g.category, "value", g.category),
            )
            for g in goals
        ],
        journey=JourneyProgress(
            grade=student.grade,
            stage_label=stage_label(student.grade),
            roadmap_percent=roadmap_percent,
        ),
        passport=passport,
        onboarding_complete=onboarding_complete,
    )


def build_insights(db: Session, student: User) -> InsightsResponse:
    """Structured direction: the ``insights`` consent section (no LLM).

    Never reads ``career_dna.sources``/``excluded`` and never touches chat,
    Letta or check-ins.

    ``profile_strength`` is taken from ``build_basic`` rather than recomputed, so
    the Overview card and the Insights card can never disagree about the same
    number -- the previous implementation returned passport completion here and
    a different blend on the student dashboard.
    """
    from app.services.careers import list_career_matches
    from app.services.dashboard import progress_indicators

    dna = db.scalar(select(CareerDNA).where(CareerDNA.user_id == student.id))
    matches = list_career_matches(db, student)
    top_matches = [m.career.title for m in matches if m.career][:MAX_MATCHES]

    # `status` is the student's current direction label; the indicator helper is
    # the existing source of truth for it.
    status = progress_indicators(db, student).get("career_direction")

    basic = build_basic(db, student)
    focus = _dna_themes(dna)[:MAX_FOCUS]

    return InsightsResponse(
        student=student_ref(student),
        scopes=[],
        status=status,
        focus_areas=focus,
        top_interests=[str(v) for v in (dna.interests or [])][:MAX_INTERESTS] if dna else [],
        strengths=[str(v) for v in (dna.strengths or [])][:MAX_INTERESTS] if dna else [],
        career_zones=[str(v) for v in (dna.career_zones or [])][:MAX_INTERESTS] if dna else [],
        top_career_matches=top_matches,
        profile_strength=basic.profile_strength,
        university_readiness=basic.university_readiness,
        passport_items=_passport_items(db, student.id),
    )


def build_growth(db: Session, student: User, today: date | None = None) -> GrowthHistory:
    """Parent-safe "Growth history" -- the replacement for "Long-term memory".

    Reads ONLY ``growth_milestones`` and ``growth_snapshots``, two tables the
    student owns and which contain no chat, no Letta content and no free-text
    check-ins. There is deliberately no Letta call anywhere in this function.
    """
    today = today or date.today()

    rows = db.execute(
        select(GrowthMilestone.title, GrowthMilestone.completed_at)
        .where(
            GrowthMilestone.user_id == student.id,
            GrowthMilestone.status == "done",
        )
        .order_by(GrowthMilestone.completed_at.desc(), GrowthMilestone.id.desc())
        .limit(MAX_MILESTONES)
    ).all()

    milestones = [
        GrowthMilestoneOut(title=str(title), completed_at=completed_at)
        for title, completed_at in rows
        if title
    ]

    total_done = db.scalar(
        select(func.count(GrowthMilestone.id)).where(
            GrowthMilestone.user_id == student.id,
            GrowthMilestone.status == "done",
        )
    )

    since = today - timedelta(days=TREND_DAYS)
    snaps = db.execute(
        select(GraphSnapshot.snapshot_date, GraphSnapshot.payload)
        .where(
            GraphSnapshot.user_id == student.id,
            GraphSnapshot.snapshot_date >= since,
        )
        .order_by(GraphSnapshot.snapshot_date.asc())
    ).all()

    trend: list[GrowthTrendPoint] = []
    for day, payload in snaps:
        value = _mean_confidence(payload)
        if value is not None:
            trend.append(GrowthTrendPoint(day=day, value=value))

    change: int | None = None
    if len(trend) >= 2:
        change = int(round(trend[-1].value - trend[0].value))

    return GrowthHistory(
        completed_milestones=milestones,
        strength_trend=trend,
        # None, never 0: "no milestones yet" is an empty state, not a zero.
        milestones_completed=int(total_done) if total_done else None,
        trend_change=change,
    )


def _mean_confidence(payload) -> int | None:
    """Mean of every confidence value in a growth snapshot payload.

    ``payload`` is ``{dimension: {label: confidence}}``. Returns None for an
    empty/garbage payload so a blank snapshot never becomes a fake "0%".
    """
    if not isinstance(payload, dict):
        return None
    values: list[float] = []
    for bucket in payload.values():
        if isinstance(bucket, dict):
            for value in bucket.values():
                if isinstance(value, (int, float)):
                    values.append(float(value))
        elif isinstance(bucket, (int, float)):
            values.append(float(bucket))
    if not values:
        return None
    return int(round(sum(values) / len(values)))


# --------------------------------------------------------------------------- composition
def _granted(link, scope: str) -> bool:
    return bool(getattr(link, "has_scope", lambda _s: False)(scope))


def build_overview(db: Session, student: User, link) -> OverviewResponse:
    """``basic`` overview, gated. Unshared -> ``basic=None`` (not an error)."""
    return OverviewResponse(
        student=student_ref(student),
        scopes=list(link.scope_names or []),
        basic=build_basic(db, student) if _granted(link, "basic") else None,
    )


def build_insights_section(db: Session, student: User, link) -> InsightsResponse:
    """``insights`` section. Unshared -> a payload with empty/None fields only."""
    response = InsightsResponse(
        student=student_ref(student),
        scopes=list(link.scope_names or []),
    )
    if not _granted(link, "insights"):
        return response

    built = build_insights(db, student)
    built.scopes = response.scopes
    return built


def build_growth_section(db: Session, student: User, link) -> GrowthHistory | None:
    """``memory``-keyed Growth history. Unshared -> ``None``."""
    if not _granted(link, "memory"):
        return None
    return build_growth(db, student)


# --------------------------------------------------------------------------- snapshot
def consented_snapshot(db: Session, student: User, link) -> dict:
    """The parent-safe dict handed to the LLM (insight + advisor).

    Built ONLY from sections the student has actually shared, so revoking a
    section immediately removes its content from the prompt -- and changes the
    insight cache key, since the key is a hash of exactly this dict.

    Contains no chat, no Letta, no check-ins, no DNA sources, no quotes.
    """
    snapshot: dict = {
        "first_name": student.first_name or "",
        "grade": student.grade,
    }

    if _granted(link, "basic"):
        basic = build_basic(db, student)
        snapshot["basic"] = {
            "school": basic.school,
            "career_direction": basic.career_direction,
            "profile_strength": basic.profile_strength,
            "university_readiness": basic.university_readiness,
            "themes": list(basic.dna_snapshot.themes) if basic.dna_snapshot else [],
            "goals": [{"title": g.title, "category": g.category} for g in basic.goals],
            "journey_stage": basic.journey.stage_label if basic.journey else None,
            "roadmap_percent": basic.journey.roadmap_percent if basic.journey else None,
            "passport_total": basic.passport.total if basic.passport else 0,
            "passport_verified": basic.passport.verified if basic.passport else 0,
            "passport_by_category": dict(basic.passport.by_category) if basic.passport else {},
            "onboarding_complete": basic.onboarding_complete,
        }

    if _granted(link, "insights"):
        insights = build_insights(db, student)
        snapshot["insights"] = {
            "status": insights.status,
            "focus_areas": list(insights.focus_areas),
            "top_interests": list(insights.top_interests),
            "strengths": list(insights.strengths),
            "career_zones": list(insights.career_zones),
            "top_career_matches": list(insights.top_career_matches),
            # Titles only, not descriptions: the advisor can be asked "what has
            # she added to her passport" and answer from the names, without the
            # LLM ever holding a full paragraph of the student's writing.
            "passport_titles": [i.title for i in insights.passport_items],
        }

    if _granted(link, "memory"):
        growth = build_growth(db, student)
        snapshot["growth"] = {
            "completed_milestones": [m.title for m in growth.completed_milestones],
            "milestones_completed": growth.milestones_completed,
            "strength_trend_change": growth.trend_change,
        }

    return snapshot


# --------------------------------------------------------------------------- audit log
def log_read(parent_id: int, student_id: int, sections_served: list[str]) -> None:
    """Structured audit line for every parent dashboard read. No new table."""
    logger.info(
        "parent_dashboard_read parent_id=%s student_id=%s sections=%s sections_served=%s",
        parent_id,
        student_id,
        ",".join(SNAPSHOT_SECTIONS),
        ",".join(sorted(sections_served)) or "none",
    )