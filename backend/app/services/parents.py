
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LinkStatus
from app.models.roadmap import RoadmapItem
from app.models.user import ParentStudentLink, User
from app.llm import prompts
from app.schemas.dashboard import ParentChildSummary
from app.services import parent_links
from app.services import roadmap as roadmap_svc
from app.services import universities as uni_svc
from app.services.career_dna import get_dna
from app.services.dashboard import progress_indicators
from app.services.providers import fallback_insight, gemini


def request_link(db: Session, parent: User, student_email: str) -> ParentStudentLink:
    """Legacy instant-link entry point (POST /parents/link).

    Now delegates to the consent flow: a link is created PENDING and must be
    approved by the student. The old behavior -- silently gaining access to a
    student by knowing their email -- is exactly what this prompt removes.

    The returned link is echoed to the caller only so the UI can tell "you are
    connected" apart from "request sent"; it never reveals whether the target
    email belongs to an existing account.
    """
    return parent_links.create_pending_link(db, parent, student_email)


def linked_students(db: Session, parent: User) -> list[User]:
    """Students this parent has an ACTIVE link to.

    Only ``status='active'`` links count: a pending link means the student has
    not consented, and a revoked link must lose access immediately. Applying the
    filter here (rather than per endpoint) means the legacy dashboard/advisor
    routes cannot accidentally serve unapproved or withdrawn students.
    """
    rows = db.scalars(
        select(User)
        .join(ParentStudentLink, ParentStudentLink.student_id == User.id)
        .where(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.status == LinkStatus.ACTIVE,
        )
    )
    return list(rows)


def child_summary(db: Session, child: User) -> dict:
    dna = get_dna(child, db)
    progress = progress_indicators(db, child)
    matches = uni_svc.recent_matches(db, child)
    improvements = []
    if matches:
        improvements = matches[0].improvements or []
    if not improvements:
        grade_items = [
            i.title for i in db.scalars(
                select(RoadmapItem).where(
                    RoadmapItem.user_id == child.id,
                    RoadmapItem.completed.is_(False),
                    RoadmapItem.grade >= (child.grade or 9),
                )
            )
        ][:3]
        improvements = grade_items

    career = None
    from app.services.careers import list_career_matches

    cm = list_career_matches(db, child)
    if cm:
        career = cm[0].career.title

    insight = fallback_insight(
        child.first_name or "your child", child.grade,
        {"interests": (dna.interests or []) if dna else [], "career_zones": (dna.career_zones or []) if dna else []},
        career,
    )
    return ParentChildSummary(
        name=child.display_name,
        grade=child.grade,
        career_direction=progress["career_direction"],
        profile_strength=progress["profile_strength"],
        university_readiness=progress["university_readiness"],
        month_focus=improvements,
        insight=insight,
    ).model_dump()


def parent_dashboard(db: Session, parent: User) -> dict:
    children = linked_students(db, parent)
    summaries = [child_summary(db, c) for c in children]
    insight = (
        f"{summaries[0]['name']} is {summaries[0]['career_direction'].lower()} on their journey. "
        f"Profile strength is {summaries[0]['profile_strength']}% — keep encouraging real-world experiences over certificates."
        if summaries
        else "Link a student to start following their journey."
    )
    return {"children": summaries, "insight": insight}


async def advisor(db: Session, parent: User, question: str, child_id: int | None) -> str:
    children = linked_students(db, parent)
    child = None
    if child_id:
        child = next((c for c in children if c.id == child_id), None)
    elif children:
        child = children[0]

    if not child:
        return "Link a student to your account first so I can answer with context."

    child_context = {
        "name": child.display_name,
        "grade": child.grade,
        "school": child.school,
        "progress_summary": progress_indicators(db, child),
        "top_career": None,
    }
    try:
        from app.services.careers import list_career_matches

        cm = list_career_matches(db, child)
        if cm:
            child_context["top_career"] = cm[0].career.title
            child_context["career_fit"] = round(cm[0].score)
    except Exception as exc:
        print(f"[parents] career context skipped: {exc}")

    try:
        answer = await gemini.complete(
            prompts.parent_advisor_prompt(question, child_context),
            system=prompts.PARENT_ADVISOR_SYSTEM,
        )
        return answer
    except Exception as exc:
        print(f"[parents] advisor failed: {exc}")
        return (
            f"Here's what I can tell you about {child.first_name}: they're currently "
            f"{child_context['progress_summary']['career_direction'].lower()} on their journey "
            f"with a profile strength of {child_context['progress_summary']['profile_strength']}%. "
            "The best thing to do right now is keep encouraging exploration and real projects."
        )