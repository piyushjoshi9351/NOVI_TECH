"""Conversational onboarding API — the only onboarding engine (15 steps).

Reads the ONBOARDING_STEPS registry (app/onboarding/steps.py) and the onboarding
tables (users.onboarding_step, onboarding_answers, student_profile, countries,
curriculums, grades, subjects) to serve the 15-step flow.

- GET  /state            -> current step (options pre-resolved server-side)
- GET  /countries        -> country rows
- GET  /curriculums      -> curriculums for a country_code
- GET  /grades           -> grades for country_code + curriculum_id
- GET  /subjects         -> subjects for country_code + curriculum_id + grade_id
- POST /answer           -> validate + save an answer, advance, return next step

Compatibility adapters kept so the flow + voice frontend and clients that spoke
the legacy flow protocol keep working:

- GET  /flow             -> flow-state shape (started/done/percent/current/...)
- POST /flow/start       -> reset-free "make sure a flow exists"
- POST /flow/answer      -> legacy answer protocol ({step_id, answer|values})
- POST /flow/skip        -> record a skip and advance
- POST /flow/reset       -> wipe this student's onboarding + start again
- POST /voice/speak      -> ElevenLabs TTS (StreamingResponse)
- POST /voice/transcribe -> ElevenLabs STT
- POST /voice/answer     -> resolve spoken answer to a valid value + submit

AI-assisted steps ("university", "career_name", "career_reason", "primary_goal") ask
the student's LettA agent for a short reply; the durable facts are then extracted
deterministically and persisted in-process onto the student profile (the same fields
the registered LettA tools POST to via the internal/ onboarding endpoints). If LettA
is unreachable the steps still complete with a fallback reply.

Completing the last step kicks off a background finalize: Career DNA refresh,
career matching, passport refresh and an auto-generated roadmap, all grounded in
the 15-step context (see _finalize_after_onboarding).
"""

from datetime import datetime, timezone
import asyncio
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_student
from app.letta_client import send_onboarding_message
from app.models.catalog import Country, Curriculum, Grade, Subject
from app.models.onboarding_data import OnboardingAnswer, StudentProfile
from app.models.user import User
from app.onboarding.steps import ONBOARDING_STEPS, InputType, StepType
from app.services import voice, voice_resolve
from app.services.student_context import career_in_mind_phrase, load_student_context

logger = logging.getLogger("novi.onboarding")


def _ensure_student_memory(user: User, db: Session) -> str | None:
    """Use the same agent for onboarding, chat, core and archival memory."""
    from app.services.chat import _lazy_ensure_agent

    try:
        return _lazy_ensure_agent(user, db)
    except Exception as exc:
        logger.warning("could not provision Letta agent for student %s: %s", user.id, exc)
        return None

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Sentinel stored in users.onboarding_step once the flow is past the last step.
DONE_STEP = "completed"

AI_ASSISTED_STEPS = {"university", "career_name", "career_reason", "primary_goal"}

# Server-side option lists for the static:* options_source values. Expanded later.
STATIC_OPTIONS = {
    "saturday_activities": [
        "Hanging out with friends",
        "Gaming",
        "Sports",
        "Reading or watching something",
        "Creating art or music",
        "Exploring outdoors",
        "Coding or building things",
        "Helping out at home",
        "Cooking or baking",
        "Something else",
    ],
    "strengths": [
        "Creative",
        "Kind and patient",
        "A leader",
        "Good at sports",
        "Good with technology",
        "Curious and always learning",
        "A good friend",
        "Good at explaining things",
        "Organised",
        "Good at solving problems",
        "Another strength",
    ],
    "learning_style": [
        "Watch a video or listen to an explanation",
        "Read or take notes",
        "Try it hands-on",
        "Talk or write it through with someone",
        "Do practice questions",
        "Teach it to someone else",
        "Another way",
    ],
    "confidence": [
        "Usually confident",
        "Confident about some things",
        "Often doubt myself",
        "Better when I prepare first",
        "Hard to choose",
        "Something else",
    ],
    "career_stage": [
        "Yes, definitely",
        "I have a clear idea",
        "I have a few ideas",
        "No idea",
        "Rather not say",
    ],
}

# Novel transition line LettA is asked for on AI-assisted steps; used verbatim
# when LettA is unreachable or answers with no plain text.
FALLBACK_REPLIES = {
    "university": "Got it — I've noted that university down.",
    "career_name": "Nice — I've noted that down. What's drawing you to it?",
    "career_reason": "That's really helpful. What's one thing you'd want Novi to help you with?",
    "primary_goal": "Got it! I'll keep that front and center for you.",
}


def _clean_university_text(text: str) -> str:
    """Drop common intro phrasing so "I want to study at Stanford" -> "Stanford"."""
    cleaned = re.sub(
        r"^(?:i\s+)?(?:would\s+)?(?:love|want|like|hope|dream of)\s+.*?\b(?:to\s+)?(?:study|go|join|attend)\s+(?:at|to)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:my|the)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or text.strip()


def _extract_facts(step: dict, value: Any) -> dict | None:
    """Deterministic extraction of the durable facts the AI-assisted steps feed
    into student_profile (written through the same internal endpoints the LettA
    tools call)."""
    step_id = step["id"]
    text = str(value).strip()

    if step_id in ("career_name", "career_reason", "primary_goal"):
        if not text:
            return None
        if step_id == "career_name":
            return {"career_name": text, "interest_reason_summary": ""}
        if step_id == "career_reason":
            return {"career_name": "", "interest_reason_summary": text}
        return {"goal_summary": text}

    if step_id == "university":
        if not text:
            return None
        m = re.match(r"^(.*?)\s*[,;\n]\s*(.+)$", text) or re.match(
            r"^(.*?\S+)\s+in\s+(\S.*)$", text
        )
        if m:
            name, location = m.group(1).strip(), m.group(2).strip()
        else:
            name, location = text.rstrip(".!?"), ""
        name = _clean_university_text(name)
        if not name:
            return None
        return {
            "university_name": name,
            "location": location,
            "confidence": "high" if name and location else "low",
        }

    return None


def _persist_extracted(profile: StudentProfile, step_id: str, payload: dict) -> None:
    """Persist extracted facts onto the StudentProfile in-process.

    Mirrors exactly what the internal/onboarding endpoints write (the same fields
    the registered LettA tools POST to), but without a self-HTTP round-trip so it
    can never deadlock on the event loop during the flow request.
    """
    if profile is None:
        return
    if step_id == "university":
        profile.university_name = payload.get("university_name")
        profile.university_location = payload.get("location")
        profile.university_extraction_conf = payload.get("confidence")
    elif step_id == "career_name":
        profile.career_name = payload.get("career_name")
    elif step_id == "career_reason":
        profile.career_interest_reason = payload.get("interest_reason_summary")
    elif step_id == "primary_goal":
        profile.primary_goal = payload.get("goal_summary")


def _sync_user_from_profile(db: Session, user: User, profile: StudentProfile | None) -> None:
    """Propagate stable onboarding facts onto the auth account in the same
    transaction as the answer, so the dashboard/profile and every downstream
    feature see the student's name + grade immediately after onboarding."""
    if profile is None:
        return
    if not user.first_name and profile.preferred_name:
        user.first_name = profile.preferred_name
    if user.grade is None and profile.grade_id:
        grade = db.get(Grade, profile.grade_id)
        if grade is not None and grade.normalized_level:
            try:
                user.grade = int(grade.normalized_level)
            except (TypeError, ValueError):
                pass


class AnswerIn(BaseModel):
    step_id: str
    value: Any = None


def _step_by_id(step_id: str) -> dict | None:
    return next((s for s in ONBOARDING_STEPS if s["id"] == step_id), None)


def _current_step(user: User) -> dict | None:
    step_id = user.onboarding_step or ONBOARDING_STEPS[0]["id"]
    step = _step_by_id(step_id)
    if step is None:
        # Stale pointer (e.g. a pre-15-step onboarding_step id) -> restart cleanly.
        user.onboarding_step = ONBOARDING_STEPS[0]["id"]
        return ONBOARDING_STEPS[0]
    return step


def _profile(db: Session, user: User) -> StudentProfile | None:
    return db.get(StudentProfile, user.id)


def _options(db: Session, step: dict, profile: StudentProfile | None) -> list[dict]:
    """Resolve server-side options for a step, cascading on prior answers.

    The frontend never chains calls: whatever step /state returns already has
    the correct, filtered options.
    """
    source = step.get("options_source") or ""
    has = lambda profile, attr: profile is not None and getattr(profile, attr) is not None

    if source == "countries":
        rows = db.scalars(select(Country).order_by(Country.name)).all()
        return [{"value": r.code, "label": r.name} for r in rows]

    if source == "curriculums":
        if has(profile, "country_code"):
            rows = db.scalars(
                select(Curriculum)
                .where(Curriculum.country_code == profile.country_code)
                .order_by(Curriculum.name)
            ).all()
            return [{"value": r.id, "label": r.name} for r in rows]
        return []

    if source == "grades":
        if has(profile, "country_code") and has(profile, "curriculum_id"):
            rows = db.scalars(
                select(Grade).where(
                    Grade.country_code == profile.country_code,
                    Grade.curriculum_id == profile.curriculum_id,
                )
            ).all()
            ordered = sorted(rows, key=lambda r: int(r.normalized_level or 0))
            return [{"value": r.id, "label": r.label} for r in ordered]
        return []

    if source == "subjects":
        if has(profile, "country_code") and has(profile, "curriculum_id") and has(profile, "grade_id"):
            rows = db.scalars(
                select(Subject).where(
                    Subject.country_code == profile.country_code,
                    Subject.curriculum_id == profile.curriculum_id,
                    Subject.grade_id == profile.grade_id,
                ).order_by(Subject.name)
            ).all()
            return [{"value": r.id, "label": r.name} for r in rows]
        return []

    if source.startswith("static:"):
        key = source.split(":", 1)[1]
        return [{"value": label, "label": label} for label in STATIC_OPTIONS.get(key, [])]

    return []


def _validate(step: dict, value: Any, options: list[dict]) -> None:
    input_type = step["input_type"]
    valid_values = {o["value"] for o in options}

    if input_type == InputType.TEXT:
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(status_code=422, detail="Expected a text answer")
        return

    if input_type in (InputType.SINGLE_SELECT, InputType.SEARCHABLE_SELECT):
        if not isinstance(value, str) or value not in valid_values:
            raise HTTPException(status_code=422, detail="Value must be one of the provided options")
        return

    if input_type == InputType.MULTI_SELECT:
        if not isinstance(value, list) or not value:
            raise HTTPException(status_code=422, detail="Select at least one option")
        if not all(isinstance(v, str) for v in value):
            raise HTTPException(status_code=422, detail="All selections must be valid options")
        # The conversational frontend lets students pick an "Other"/"Something
        # else" option and type their own value, which is submitted as one
        # free-text entry alongside (or instead of) the canned options.
        custom = [v for v in value if v not in valid_values]
        if len(custom) > 1:
            raise HTTPException(status_code=422, detail="All selections must be valid options")
        return

    raise HTTPException(status_code=422, detail="Unsupported input type")


def _prefill(db: Session, user: User, step: dict) -> Any:
    ans = db.scalar(
        select(OnboardingAnswer)
        .where(
            OnboardingAnswer.student_id == user.id,
            OnboardingAnswer.step_id == step["id"],
        )
        .order_by(OnboardingAnswer.created_at.desc(), OnboardingAnswer.id.desc())
        .limit(1)
    )
    return ans.raw_value if ans else None


def _state_payload(db: Session, step: dict, user: User, profile: StudentProfile | None = None) -> dict:
    profile = profile if profile is not None else _profile(db, user)
    return {
        "step_id": step["id"],
        "order": step["order"],
        "type": step["type"].value,
        "question": step["question"],
        "input_type": step["input_type"].value,
        "options": _options(db, step, profile),
        "prefill": _prefill(db, user, step),
    }


@router.get("/state")
def onboarding_state(
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    # Create Letta agent if needed (first time hitting state or answer).
    # If LettA is unavailable the flow still works — the AI steps degrade to the
    # deterministic fallback and LettA is retried on the next request.
    _ensure_student_memory(user, db)

    step = _current_step(user)
    if step is None:
        return {"completed": True}
    return _state_payload(db, step, user)


@router.get("/countries")
def list_countries(
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    rows = db.scalars(select(Country).order_by(Country.name)).all()
    return [{"code": r.code, "name": r.name} for r in rows]


@router.get("/curriculums")
def list_curriculums(
    country_code: str = Query(..., description="ISO 3166 alpha-2 country code"),
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Curriculum).where(Curriculum.country_code == country_code).order_by(Curriculum.name)
    ).all()
    return [{"id": r.id, "country_code": r.country_code, "name": r.name} for r in rows]


@router.get("/grades")
def list_grades(
    country_code: str = Query(...),
    curriculum_id: str = Query(...),
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Grade).where(
            Grade.country_code == country_code,
            Grade.curriculum_id == curriculum_id,
        )
    ).all()
    ordered = sorted(rows, key=lambda r: int(r.normalized_level or 0))
    return [
        {"id": r.id, "country_code": r.country_code, "curriculum_id": r.curriculum_id,
         "label": r.label, "normalized_level": r.normalized_level}
        for r in ordered
    ]


@router.get("/subjects")
def list_subjects(
    country_code: str = Query(...),
    curriculum_id: str = Query(...),
    grade_id: str = Query(...),
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Subject).where(
            Subject.country_code == country_code,
            Subject.curriculum_id == curriculum_id,
            Subject.grade_id == grade_id,
        ).order_by(Subject.name)
    ).all()
    return [
        {"id": r.id, "country_code": r.country_code, "curriculum_id": r.curriculum_id,
         "grade_id": r.grade_id, "name": r.name}
        for r in rows
    ]


@router.post("/answer")
async def submit_answer(
    data: AnswerIn,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    # Ensure Letta agent exists
    _ensure_student_memory(user, db)

    step = _step_by_id(data.step_id)
    current = _current_step(user)
    if step is None or current is None or step["id"] != current["id"]:
        raise HTTPException(status_code=404, detail="Step not found or not the current step")

    profile = _profile(db, user)
    options = _options(db, step, profile)
    _validate(step, data.value, options)

    db.add(OnboardingAnswer(student_id=user.id, step_id=step["id"], raw_value=data.value))

    if profile is None:
        profile = StudentProfile(student_id=user.id)
        db.add(profile)

    letta_reply = None

    if step["type"] == StepType.DETERMINISTIC:
        if step["id"] == "career":
            profile.has_career_in_mind = data.value != "No idea"
        else:
            setattr(profile, step["save_field"], data.value)
    else:  # AI_ASSISTED
        if step["id"] == "university":
            profile.university_raw_text = data.value

        # 1) Ask LettA to extract + reply (best-effort). LettA's own agent loop
        #    can't reliably run tools against Gemini 3.x (MEMORY_SYSTEM.md §1),
        #    so a quiet failure here must not block the onboarding.
        letta_reply = None
        if user.letta_agent_id:
            letta_reply = send_onboarding_message(user.letta_agent_id, step["id"], data.value)

        # 2) Persist the durable facts through the internal endpoints (the same
        #    routes the registered LettA tools POST to). Deterministic so the
        #    extracted profile lands regardless of the agent loop state.
        extracted = _extract_facts(step, data.value)
        if extracted:
            if step["id"] == "career_reason" and profile:
                extracted["career_name"] = profile.career_name or ""
            try:
                _persist_extracted(profile, step["id"], extracted)
                logger.info("persisted onboarding step '%s' for student %s", step["id"], user.id)
            except Exception as exc:
                logger.warning("failed to persist step '%s' for student %s: %s", step["id"], user.id, exc)

        # 3) Reply line: LettA's own words when it answered, else a warm line.
        if not letta_reply:
            letta_reply = FALLBACK_REPLIES.get(step["id"], "Got it — let's keep going!")

    # Handle branching after "career" step
    # If career answer is "No idea", skip career_name and career_reason, go to primary_goal
    if step["id"] == "career":
        if data.value != "No idea":
            # Has career in mind -> go to career_name
            career_idx = next(i for i, s in enumerate(ONBOARDING_STEPS) if s["id"] == "career")
            nxt = ONBOARDING_STEPS[career_idx + 1]  # career_name
        else:
            # No idea -> skip to primary_goal
            nxt = _step_by_id("primary_goal")
    elif step["id"] in ("career_name", "career_reason"):
        # Normal progression through the new career sub-steps
        idx = ONBOARDING_STEPS.index(step)
        nxt = ONBOARDING_STEPS[idx + 1] if idx + 1 < len(ONBOARDING_STEPS) else None
    else:
        # All other steps use normal sequential progression
        idx = ONBOARDING_STEPS.index(step)
        nxt = ONBOARDING_STEPS[idx + 1] if idx + 1 < len(ONBOARDING_STEPS) else None

    _sync_user_from_profile(db, user, profile)

    if nxt is None:
        user.onboarding_step = DONE_STEP
        user.onboarding_completed_at = datetime.now(timezone.utc)
        db.commit()
        _schedule_finalize(user.id)
        return {"completed": True}

    user.onboarding_step = nxt["id"]
    db.commit()
    
    payload = _state_payload(db, nxt, user, profile)
    if letta_reply:
        payload["letta_reply"] = letta_reply
    return payload


# ---------------------------------------------------------------------------
# Flow-protocol compatibility adapters (the legacy flow frontend shape)
# ---------------------------------------------------------------------------

class FlowAnswerIn(BaseModel):
    step_id: str
    answer: str | None = None
    values: list[str] | None = None


class SkipIn(BaseModel):
    step_id: str


def _answers(db: Session, user: User) -> list[OnboardingAnswer]:
    return list(
        db.scalars(
            select(OnboardingAnswer)
            .where(OnboardingAnswer.student_id == user.id)
            .order_by(OnboardingAnswer.id)
        )
    )


def _is_skip(raw) -> bool:
    return isinstance(raw, dict) and bool(raw.get("skipped"))


def _value_text(raw) -> str:
    if raw is None:
        return ""
    if _is_skip(raw):
        return "⏭ Skipped"
    if isinstance(raw, list):
        return ", ".join(str(v) for v in raw)
    if isinstance(raw, dict):
        return ", ".join(f"{k}: {v}" for k, v in raw.items() if k != "skipped")
    return str(raw).strip()


def _legacy_kind(input_type: InputType) -> str:
    if input_type == InputType.MULTI_SELECT:
        return "multi"
    if input_type == InputType.TEXT:
        return "free"
    return "single"


def _legacy_step(db: Session, user: User, step: dict) -> dict | None:
    options = _options(db, step, _profile(db, user))
    return {
        "id": step["id"],
        "question": step["question"],
        "kind": _legacy_kind(step["input_type"]),
        "options": [o["label"] for o in options],
        "optional": False,
        "max_select": None,
        "hint": None,
        "section": "onboarding",
    }


def _flow_transcript(answers: list[OnboardingAnswer]) -> list[dict]:
    by_id = {s["id"]: s for s in ONBOARDING_STEPS}
    out: list[dict] = []
    for a in answers:
        step = by_id.get(a.step_id)
        if not step:
            continue
        out.append({"role": "assistant", "content": step["question"]})
        out.append({"role": "user", "content": _value_text(a.raw_value)})
    return out


def _completion_summary(db: Session, user: User, answers: list[OnboardingAnswer]) -> dict:
    ctx = load_student_context(db, user)
    career = career_in_mind_phrase(ctx)
    return {
        "archetype": "profile ready",
        "status": "complete",
        "message": "Onboarding complete! Novi has your profile ready — check your DNA, careers and roadmap.",
        "traits": (ctx.get("strengths") or [])[:3],
        "career_zones": [career] if career else (ctx.get("interests") or [])[:2],
        "interests": (ctx.get("interests") or [])[:4],
        "subjects": (ctx.get("subjects_enjoyed") or [])[:4],
        "goal": (ctx.get("goal_vision") or ctx.get("help_wish") or career or "Build a stronger profile"),
    }


def _flow_state(db: Session, user: User) -> dict:
    done = user.onboarding_step == DONE_STEP
    answers = _answers(db, user)
    answered = sum(1 for a in answers if not _is_skip(a.raw_value))
    total = len(ONBOARDING_STEPS)
    current = None if done else _legacy_step(db, user, _current_step(user))
    return {
        "started": True,
        "done": done,
        "status": "done" if done else "active",
        "conversation_id": None,
        "percent": min(100, round(answered / total * 100) if total else 0),
        "answered": answered,
        "total": total,
        "current": current,
        "transcript": _flow_transcript(answers),
        "summary": _completion_summary(db, user, answers) if done else None,
        "error": None,
    }


def _submit_flow(db: Session, user: User, step_id: str, value: Any) -> dict | None:
    """Non-HTTP version of /answer's core (returns None when advance completes).

    The flow frontend submits the *displayed* option label; catalog-driven steps
    (country/curriculum/grade/subjects) use opaque codes as option values, so any
    submitted value that matches a label is mapped back to its value first. Static
    steps are identity (label == value), and free-text answers pass through.
    """
    step = _step_by_id(step_id)
    current = _current_step(user)
    if step is None or current is None or step["id"] != current["id"]:
        raise HTTPException(status_code=404, detail="Step not found or not the current step")

    profile = _profile(db, user)
    options = _options(db, step, profile)
    by_label = {o["label"]: o["value"] for o in options}
    # Keep the student's own words for the transcript/summary, while persisting
    # the normalized catalog value (e.g. subject id) onto the profile below.
    submitted = value
    if isinstance(value, list):
        value = [by_label.get(v, v) for v in value]
    elif isinstance(value, str):
        value = by_label.get(value, value)
    _validate(step, value, options)

    db.add(OnboardingAnswer(student_id=user.id, step_id=step["id"], raw_value=submitted))

    if profile is None:
        profile = StudentProfile(student_id=user.id)
        db.add(profile)

    if step["type"] == StepType.DETERMINISTIC:
        if step["id"] == "career":
            profile.has_career_in_mind = value != "No idea"
        else:
            setattr(profile, step["save_field"], value)
    else:  # AI_ASSISTED
        if step["id"] == "university":
            profile.university_raw_text = value
        if user.letta_agent_id:
            send_onboarding_message(user.letta_agent_id, step["id"], value or "")
        extracted = _extract_facts(step, value)
        if extracted:
            if step["id"] == "career_reason" and profile:
                extracted["career_name"] = profile.career_name or ""
            try:
                _persist_extracted(profile, step["id"], extracted)
                logger.info("persisted onboarding step '%s' for student %s", step["id"], user.id)
            except Exception as exc:
                logger.warning("failed to persist step '%s' for student %s: %s", step["id"], user.id, exc)

    if step["id"] == "career":
        nxt = _step_by_id("primary_goal") if value == "No idea" else _step_by_id("career_name")
    else:
        idx = ONBOARDING_STEPS.index(step)
        nxt = ONBOARDING_STEPS[idx + 1] if idx + 1 < len(ONBOARDING_STEPS) else None

    _sync_user_from_profile(db, user, profile)

    if nxt is None:
        user.onboarding_step = DONE_STEP
        user.onboarding_completed_at = datetime.now(timezone.utc)
        db.commit()
        return None

    user.onboarding_step = nxt["id"]
    db.commit()
    return _step_by_id(nxt["id"])


@router.get("/flow")
def flow_state(
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    return _flow_state(db, user)


@router.post("/flow/start")
def flow_start(
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    if not user.onboarding_step:
        user.onboarding_step = ONBOARDING_STEPS[0]["id"]
        db.commit()
    return _flow_state(db, user)


@router.post("/flow/answer")
async def flow_answer(
    data: FlowAnswerIn,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    if data.values is not None:
        value: Any = data.values
    else:
        value = data.answer
    _submit_flow(db, user, data.step_id, value)
    if user.onboarding_step == DONE_STEP:
        _schedule_finalize(user.id)
    return _flow_state(db, user)


@router.post("/flow/skip")
async def flow_skip(
    data: SkipIn,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    step = _step_by_id(data.step_id)
    current = _current_step(user)
    if step is None or current is None or step["id"] != current["id"]:
        raise HTTPException(status_code=404, detail="Step not found or not the current step")
    idx = ONBOARDING_STEPS.index(step)
    nxt = ONBOARDING_STEPS[idx + 1] if idx + 1 < len(ONBOARDING_STEPS) else None
    db.add(OnboardingAnswer(student_id=user.id, step_id=step["id"], raw_value={"skipped": True}))
    if nxt is None:
        user.onboarding_step = DONE_STEP
        user.onboarding_completed_at = datetime.now(timezone.utc)
        db.commit()
        _schedule_finalize(user.id)
        return _flow_state(db, user)
    user.onboarding_step = nxt["id"]
    db.commit()
    return _flow_state(db, user)


@router.post("/flow/reset")
def flow_reset(
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    for row in _answers(db, user):
        db.delete(row)
    user.onboarding_step = ONBOARDING_STEPS[0]["id"]
    user.onboarding_completed_at = None
    db.commit()
    return _flow_state(db, user)


# ---------------------------------------------------------------------------
# Voice (TTS / STT / spoken answers) — engine-agnostic
# ---------------------------------------------------------------------------

class SpeakIn(BaseModel):
    text: str


class VoiceAnswerIn(BaseModel):
    step_id: str
    transcript: str


def _label_to_value(options: list[dict], label: str) -> str:
    if not label:
        return ""
    for o in options:
        if o["label"] == label:
            return o["value"]
    return label


@router.post("/voice/speak")
async def voice_speak(
    data: SpeakIn,
    user: User = Depends(get_current_student),
):
    stream = voice.speak(data.text)

    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        raise HTTPException(status_code=502, detail="No audio produced")
    except voice.VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    async def _stream():
        yield first
        async for chunk in stream:
            yield chunk

    return StreamingResponse(_stream(), media_type="audio/mpeg")


@router.post("/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_student),
):
    try:
        audio = await file.read()
        text = await voice.transcribe(audio, file.filename or "audio.webm")
    except voice.VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"text": text}


@router.post("/voice/answer")
async def voice_answer(
    data: VoiceAnswerIn,
    user: User = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    step = _step_by_id(data.step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Unknown step.")

    profile = _profile(db, user)
    options = _options(db, step, profile)
    labels = [o["label"] for o in options]
    kind = _legacy_kind(step["input_type"])
    rstep = voice_resolve.Step(id=step["id"], question=step["question"], kind=kind, options=labels)
    resolved = await voice_resolve.resolve_answer(rstep, data.transcript)
    if resolved is None or (isinstance(resolved, list) and not resolved):
        return {
            "resolved": False,
            "error": "Couldn't map your spoken answer to a valid option — please try again.",
        }

    if isinstance(resolved, list):
        value = [_label_to_value(options, label) for label in resolved]
    else:
        value = _label_to_value(options, resolved)
    _submit_flow(db, user, step["id"], value)
    if user.onboarding_step == DONE_STEP:
        _schedule_finalize(user.id)
    return {"resolved": True, "resolved_value": value, **_flow_state(db, user)}


# ---------------------------------------------------------------------------
# Background completion: DNA + careers + roadmap + passport from 15-step context
# ---------------------------------------------------------------------------

def _finalize_history(db: Session, user: User) -> list[dict]:
    """Deterministic Q&A transcript reconstructed from the stored answers."""
    by_id = {s["id"]: s for s in ONBOARDING_STEPS}
    out: list[dict] = []
    for a in _answers(db, user):
        step = by_id.get(a.step_id)
        if not step or _is_skip(a.raw_value):
            continue
        out.append({"role": "assistant", "content": step["question"]})
        out.append({"role": "user", "content": _value_text(a.raw_value)})
    return out


def _schedule_finalize(user_id: int) -> None:
    """Fire-and-forget the post-onboarding finalize so the answer request returns
    instantly even when the LLM-backed steps are slow."""
    try:
        asyncio.create_task(_finalize_after_onboarding(user_id))
    except RuntimeError:  # pragma: no cover - no running loop (tests / sync callers)
        print("[onboarding] no event loop; skipping background finalize")


async def _finalize_after_onboarding(user_id: int) -> None:
    from app.core.database import SessionLocal
    from app.models.roadmap import Goal
    from app.schemas.career import CareerMatchRequest
    from app.schemas.roadmap import RoadmapGenerateRequest
    from app.services import passport as passport_service
    from app.services import roadmap as roadmap_service
    from app.services.career_dna import refresh_dna_from_history
    from app.services.careers import match_careers

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            return

        history = _finalize_history(db, user)
        if not history:
            logger.info("onboarding finalize: no answers recorded for student %s", user_id)
            return

        # Populate the DNA deterministicly from the onboarding context FIRST so
        # it is never left empty while the LLM-based refinement runs.
        try:
            from app.services.career_dna import seed_dna_from_context

            seed_dna_from_context(user, db, history)
            logger.info("onboarding finalize: Career DNA seeded for %s", user_id)
        except Exception as exc:
            print(f"[onboarding] dna seed failed: {exc}")

        try:
            await refresh_dna_from_history(user, history, db)
            logger.info("onboarding finalize: Career DNA refreshed for %s", user_id)
        except Exception as exc:
            print(f"[onboarding] dna finalize failed: {exc}")

        try:
            await match_careers(db, user, CareerMatchRequest(limit=8))
            logger.info("onboarding finalize: careers matched for %s", user_id)
        except Exception as exc:
            print(f"[onboarding] career match failed: {exc}")

        try:
            await passport_service.refresh_from_chat(db, user)
            logger.info("onboarding finalize: passport refreshed for %s", user_id)
        except Exception as exc:
            print(f"[onboarding] passport refresh failed: {exc}")

        try:
            goals = list(db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.status == "active")))
            junk = {"test answer", "test", "none", "...", "na", "n/a", "i don't know", ""}
            real = [g for g in goals if str(g.title or "").strip().lower() not in junk]
            if not real:
                ctx = load_student_context(db, user)
                title = (
                    (ctx.get("goal_vision") or ctx.get("help_wish") or career_in_mind_phrase(ctx))
                    or "Build a stronger profile"
                )
                await roadmap_service.generate_roadmap(
                    db, user, RoadmapGenerateRequest(title=str(title)[:120])
                )
                logger.info("onboarding finalize: roadmap generated for %s", user_id)
        except Exception as exc:
            print(f"[onboarding] roadmap generate failed: {exc}")
    finally:
        db.close()
