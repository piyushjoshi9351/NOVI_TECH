"""Parent-safe read models.

Everything here reads LEGACY tables directly and maps to the explicit allowlist
schemas in ``app/schemas/parent.py``. Two rules are load-bearing:

* Never read a field a parent is not entitled to. Specifically: CareerDNA
  ``sources`` (raw chat quotes + conversation ids), ``excluded``,
  ``novi_reflection``; WeeklyCheckin free text (``challenges``, ``pride``,
  ``next_week``, ``ai_summary``); any conversation/chat row; credentials; and
  ``letta_agent_id``.
* Return the schema objects, never dicts of ORM rows, so a new column cannot leak
  in by default.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.career_dna import CareerDNA
from app.models.enums import GoalStatus
from app.models.passport import PassportItem
from app.models.roadmap import RoadmapItem, WeeklyPriority
from app.models.user import User
from app.schemas.parent import (
    InsightsResponse,
    OverviewGoal,
    OverviewPassport,
    OverviewResponse,
    OverviewRoadmapItem,
    OverviewWeekly,
    ParentStudentRef,
)
from app.services import universities as uni_svc
from app.services.careers import list_career_matches
from app.services.passport import completion as passport_completion
from app.services.roadmap import list_goals

MAX_GOALS = 10
MAX_PASSPORT = 10
MAX_ROADMAP = 10


def student_ref(student: User) -> ParentStudentRef:
    return ParentStudentRef(first_name=student.first_name or "", grade=student.grade)


def _current_week_start(today: date | None = None) -> date:
    today = today or date.today()
    return today.fromordinal(today.toordinal() - today.weekday())


def build_overview(db: Session, student: User, link) -> OverviewResponse:
    """``basic`` scope: identity, goals, roadmap, passport, this week's focus."""
    goals = [
        OverviewGoal(
            id=g.id,
            title=g.title,
            category=getattr(g.category, "value", g.category),
            status=getattr(g.status, "value", g.status),
            target_date=g.target_date,
        )
        for g in list_goals(db, student)
        if g.status == GoalStatus.ACTIVE
    ][:MAX_GOALS]

    passport = [
        OverviewPassport(
            id=p.id,
            title=p.title,
            category=getattr(p.category, "value", p.category),
            date_achieved=p.date_achieved,
        )
        for p in db.scalars(
            select(PassportItem)
            .where(PassportItem.user_id == student.id)
            # MySQL has no NULLS LAST, so sort undated items to the end explicitly.
            .order_by(
                PassportItem.date_achieved.is_(None),
                PassportItem.date_achieved.desc(),
                PassportItem.id.desc(),
            )
        )
    ][:MAX_PASSPORT]

    roadmap = [
        OverviewRoadmapItem(
            id=i.id,
            title=i.title,
            grade=i.grade,
            stage=getattr(i.stage, "value", i.stage),
            category=i.category,
            completed=bool(i.completed),
        )
        for i in db.scalars(
            select(RoadmapItem)
            .where(RoadmapItem.user_id == student.id, RoadmapItem.completed.is_(False))
            .order_by(RoadmapItem.grade.asc(), RoadmapItem.order_index.asc(), RoadmapItem.id.asc())
        )
    ][:MAX_ROADMAP]

    week_start = _current_week_start()
    week_end = week_start + timedelta(days=6)
    priorities = list(
        db.scalars(
            select(WeeklyPriority)
            .where(
                WeeklyPriority.user_id == student.id,
                WeeklyPriority.week_start >= week_start,
                WeeklyPriority.week_start <= week_end,
            )
            .order_by(WeeklyPriority.ordinal.asc())
        )
    )
    this_week = OverviewWeekly(
        week_start=priorities[0].week_start if priorities else week_start,
        priorities=[p.title for p in priorities],
        completed_count=sum(1 for p in priorities if p.completed),
        total_count=len(priorities),
    )

    return OverviewResponse(
        student=student_ref(student),
        scopes=link.scope_names,
        school=student.school,
        active_goals=goals,
        recent_passport=passport,
        upcoming_roadmap=roadmap,
        this_week=this_week,
    )


def build_insights(db: Session, student: User, link) -> InsightsResponse:
    """``insights`` scope: high-level direction derived from structured data.

    Reads only the DNA's own summary fields -- never ``sources`` (which holds
    verbatim chat quotes and conversation ids) or ``excluded``.
    """
    dna = db.scalar(select(CareerDNA).where(CareerDNA.user_id == student.id))

    matches = list_career_matches(db, student)
    top_matches = [m.career.title for m in matches if m.career][:5]

    # passport_completion() returns {"score": int, ...}; we only take the score.
    completion = passport_completion(db, student)
    profile_strength = completion.get("score") if isinstance(completion, dict) else None
    readiness = uni_svc.average_readiness(db, student) or None

    return InsightsResponse(
        student=student_ref(student),
        scopes=link.scope_names,
        top_interests=list(dna.interests or [])[:8] if dna else [],
        strengths=list(dna.strengths or [])[:8] if dna else [],
        career_zones=list(dna.career_zones or [])[:8] if dna else [],
        top_career_matches=top_matches,
        profile_strength=profile_strength,
        university_readiness=readiness,
    )