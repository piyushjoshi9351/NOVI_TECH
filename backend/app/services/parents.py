"""Legacy parent service: linking, the old child summary, and "Ask Novi".

Everything here is behind the same consent gate as the v1 dashboard
(``app.services.parent_links`` for authorization,
``app.services.parent_projection`` for what may be shown).

``/parents/link`` and ``/parents/advisor`` are retained only because the existing
parent frontend still calls them; both now sit behind the consent flow and both
delegate their data access to the projection.

Advisor invariants
------------------
* The LLM's only input is ``consented_snapshot`` -- the parent-safe projection of
  the sections the student shared. It never sees chat, Letta, check-ins, DNA
  sources or quotes.
* **Stateless with respect to the student.** This module writes NOTHING to the
  student's conversations, messages, Letta memory or DNA, and a parent question
  never touches the student's memory. There is no archive/send/store call here,
  by design.
* The student is identified by FIRST NAME and grade only. The old implementation
  passed ``display_name`` (first + last) into the prompt.
* Bounded input and a per-parent rate limit, since a parent question is
  untrusted text headed for an LLM prompt.
"""

import asyncio
import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LinkStatus
from app.models.user import ParentStudentLink, User
from app.llm import prompts
from app.schemas.dashboard import ParentChildSummary
from app.schemas.parent import (
    MAX_ADVISOR_HISTORY_LEN,
    MAX_ADVISOR_HISTORY_TURNS,
    MAX_ADVISOR_QUESTION,
)
from app.services import parent_links
from app.services import parent_projection as projection
from app.services import universities as uni_svc
from app.services.career_dna import get_dna
from app.services.dashboard import progress_indicators

logger = logging.getLogger("novi.parents")

# In-process sliding window. Enough to stop a runaway client; a multi-worker
# deployment would move this to Redis, which nothing here currently depends on.
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW_SECONDS = 60.0
_rate_state: dict[int, list[float]] = {}


class RateLimited(Exception):
    """Raised when a parent exceeds the advisor rate limit."""


def check_rate_limit(parent_id: int) -> None:
    """Sliding-window per-parent limit for the advisor endpoint."""
    now = time.monotonic()
    hits = [t for t in _rate_state.get(parent_id, []) if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(hits) >= RATE_LIMIT_MAX:
        _rate_state[parent_id] = hits
        raise RateLimited()
    hits.append(now)
    _rate_state[parent_id] = hits


def reset_rate_limits() -> None:
    """Test helper."""
    _rate_state.clear()


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
    not consented, and a revoked link must lose access immediately.
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


def _active_link(db: Session, parent: User, student_id: int) -> ParentStudentLink | None:
    return db.scalar(
        select(ParentStudentLink).where(
            ParentStudentLink.parent_id == parent.id,
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.status == LinkStatus.ACTIVE,
        )
    )


def child_summary(db: Session, child: User) -> dict:
    """Child summary for the legacy parent dashboard.

    Same projections as the v1 cards -- no raw text, no DNA evidence. ``insight``
    uses the deterministic parent-voice template so this path never shows the
    student-facing chat copy the old ``fallback_insight`` produced.
    """
    dna = get_dna(child, db)
    progress = progress_indicators(db, child)
    matches = uni_svc.recent_matches(db, child)
    improvements = []
    if matches:
        improvements = matches[0].improvements or []

    career = None
    from app.services.careers import list_career_matches

    cm = list_career_matches(db, child)
    if cm:
        career = cm[0].career.title

    from app.services.parent_insight import template_insight

    link = _first_link(db, child)
    if link is not None:
        snapshot = projection.consented_snapshot(db, child, link)
    else:
        snapshot = {
            "first_name": child.first_name or "",
            "grade": child.grade,
            "insights": {
                "top_interests": list(dna.interests or []) if dna else [],
                "career_zones": list(dna.career_zones or []) if dna else [],
                "focus_areas": list(dna.career_zones or [])[:4] if dna else [],
                "top_career_matches": [career] if career else [],
            },
        }

    return ParentChildSummary(
        # First name only -- the last name is not needed and is not shared.
        name=child.first_name or "Your child",
        grade=child.grade,
        career_direction=progress["career_direction"],
        profile_strength=progress["profile_strength"],
        university_readiness=progress["university_readiness"],
        month_focus=improvements,
        insight=template_insight(snapshot),
    ).model_dump()


def _first_link(db: Session, child: User) -> ParentStudentLink | None:
    """Any active link to this student -- used only to read its consent scopes."""
    return db.scalar(
        select(ParentStudentLink)
        .where(
            ParentStudentLink.student_id == child.id,
            ParentStudentLink.status == LinkStatus.ACTIVE,
        )
        .order_by(ParentStudentLink.id.asc())
        .limit(1)
    )


def parent_dashboard(db: Session, parent: User) -> dict:
    children = linked_students(db, parent)
    summaries = [child_summary(db, c) for c in children]
    if not summaries:
        insight = "Link a student to start following their journey."
    else:
        first = summaries[0]
        insight = (
            f"{first['name']} is {str(first['career_direction']).lower()} on their journey, "
            f"with a profile strength of {first['profile_strength']}%. "
            "Encouraging real interests over credentials tends to help most at this stage."
        )
    return {"children": summaries, "insight": insight}


# --------------------------------------------------------------------------- advisor
PRIVATE_REDIRECT = (
    "That's private to your child — conversations and personal reflections "
    "between them and Novi stay between them, and I keep it that way. If it's "
    "worth raising, it's usually a good moment to ask them directly."
)


async def advisor(
    db: Session,
    parent: User,
    question: str,
    child_id: int | None,
    history: list | None = None,
) -> str:
    """Answer a parent question from the consented parent-safe snapshot only.

    Reads nothing but the projection, writes nothing, and never calls Letta.

    ``history`` is optional conversation context for multi-turn continuity. It is
    held in memory for the duration of this one call and discarded -- it is never
    written anywhere, so a parent's side of the conversation can never surface in
    the student's record. Omitting it preserves the original one-shot behaviour.
    """
    question = (question or "").strip()[:MAX_ADVISOR_QUESTION]
    if not question:
        return "Ask me anything about your child's progress and I'll answer from what they've shared."

    children = linked_students(db, parent)
    child = None
    link = None
    if child_id:
        child = next((c for c in children if c.id == child_id), None)
        if child is not None:
            link = _active_link(db, parent, child.id)
    elif children:
        child = children[0]
        if child is not None:
            link = _active_link(db, parent, child.id)

    if not child or link is None:
        return (
            "Once your child approves your request and chooses what to share, "
            "I can answer questions about their journey."
        )

    # Only consented sections -- revoking one removes it from the very next
    # answer, because the snapshot is rebuilt per request.
    snapshot = projection.consented_snapshot(db, child, link)
    turns = _clean_history(history)

    try:
        from app.services.providers import gemini

        answer = await gemini.complete(
            prompts.parent_advisor_prompt(question, snapshot, turns),
            system=prompts.PARENT_ADVISOR_SYSTEM,
        )
        if answer and answer.strip():
            return answer.strip()
    except Exception:
        logger.info("parent advisor: LLM unavailable, using deterministic answer", exc_info=True)

    return _template_answer(snapshot, turns)


def _clean_history(history) -> list[tuple[str, str]]:
    """Coerce client-supplied turns into a small, trusted-shape list.

    Defence in depth: the Pydantic schema already bounds role and length, but this
    runs before the value reaches a prompt, and it drops anything unrecognised
    rather than trusting the caller's shape.
    """
    if not history:
        return []
    out: list[tuple[str, str]] = []
    for turn in list(history)[-MAX_ADVISOR_HISTORY_TURNS:]:
        role = getattr(turn, "role", None)
        content = (getattr(turn, "content", "") or "").strip()
        if role not in ("parent", "novi") or not content:
            continue
        out.append((role, content[:MAX_ADVISOR_HISTORY_LEN]))
    return out


def _template_answer(snapshot: dict, turns: list[tuple[str, str]] | None = None) -> str:
    """Deterministic fallback so the advisor never errors on an AI outage.

    Kept deliberately vague-but-useful: it must never fabricate a fact the
    snapshot does not contain. With conversation history in hand it acknowledges
    the thread rather than repeating its opening line verbatim, so a long chat
    does not visibly stall on an AI outage.
    """
    name = (snapshot.get("first_name") or "").strip() or "your child"
    basic = snapshot.get("basic") or {}
    insights = snapshot.get("insights") or {}

    bits: list[str] = []
    direction = basic.get("career_direction") or insights.get("top_career_matches", [None])[0]
    if direction:
        bits.append(f"{name} is currently exploring {direction}")
    strength = basic.get("profile_strength")
    if strength is not None:
        bits.append(f"their profile is about {strength}% complete")

    if not bits:
        return (
            f"There's not much shared about {name} yet — they've chosen which parts "
            "of their journey you can see. Once they share more, I can be more "
            "specific. In the meantime, asking what they're enjoying is a great "
            "place to start."
        )

    # Mid-conversation: acknowledge rather than re-open.
    if turns:
        return (
            f"Still the same on my side: {' and '.join(bits)}. I'm answering from the "
            "same shared summary as before, so anything you'd like me to look at from "
            "a different angle, just ask."
        )
    return (
        f"Right now {' and '.join(bits)}. The most useful thing you can do right now "
        "is keep asking what they're enjoying and what they'd like to try next — "
        "that keeps the decisions in their hands."
    )