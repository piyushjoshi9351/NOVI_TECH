"""Novi's Insight card for the parent Overview.

Three properties this module exists to guarantee:

1. **Parent voice.** The card is written to a parent about their child. The old
   implementation reused ``providers.fallback_insight``, which produces
   student-facing chat copy ("...keep coming up for Prateek. Want to explore what
   that path actually looks like?") and was leaking straight into the parent
   view. There is a dedicated, deterministic fallback here instead.

2. **Consent-scoped input.** The LLM only ever sees
   ``parent_projection.consented_snapshot`` -- the parent-safe projection of the
   sections the student actually shared. It structurally cannot see chat, Letta,
   check-ins, DNA sources or quotes.

3. **Consent-scoped cache.** The cache key is a SHA-256 of that snapshot. Because
   the snapshot contains only consented data, revoking a section changes the key,
   so content derived from the revoked section is never served again. TTL 24h.

Fails soft everywhere: an LLM error falls back to a template, a DB error falls
back to a template, so the card can never 500 the dashboard.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.llm import prompts
from app.models.parent_insight_cache import ParentInsightCache
from app.models.user import ParentStudentLink, User
from app.services.parent_projection import consented_snapshot

logger = logging.getLogger("novi.parent_insight")

TTL_HOURS = 24
# Keep the cached copy well under any column limit even if the model rambles.
MAX_INSIGHT_CHARS = 600


def snapshot_hash(snapshot: dict) -> str:
    """Stable key for a consented snapshot.

    ``sort_keys`` makes the hash independent of dict ordering, so the same data
    always hits the cache; ``default=str`` covers the date values inside the
    snapshot. Only consented data is hashed -- that is what makes revocation
    invalidate immediately.
    """
    blob = json.dumps(snapshot, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- template
def template_insight(snapshot: dict) -> str:
    """Deterministic parent-voice note. Always available, never fails.

    Deliberately plain: it only restates facts already in the snapshot, so it
    can never invent anything even when the LLM is down.
    """
    name = (snapshot.get("first_name") or "").strip()
    subject = name or "Your child"

    if not any(k in snapshot for k in ("basic", "insights", "growth")):
        return (
            f"There's not much to share about {subject} just yet — they've chosen "
            "which parts of their journey you can see, and that's completely their call."
        )

    insights = snapshot.get("insights") or {}
    basic = snapshot.get("basic") or {}

    themes: list[str] = []
    for bucket in ("focus_areas", "top_career_matches", "career_zones", "strengths"):
        themes.extend(insights.get(bucket) or [])
    themes.extend(basic.get("themes") or [])
    seen: set[str] = set()
    themes = [t for t in (str(x).strip() for x in themes) if t and not (t.lower() in seen or seen.add(t.lower()))]

    milestones = (snapshot.get("growth") or {}).get("milestones_completed") or 0
    stage = basic.get("journey_stage")

    parts: list[str] = []
    if themes:
        parts.append(f"{subject} is showing real interest in {themes[0]}")
        if len(themes) > 1:
            parts[-1] += f", and {themes[1]}"
        parts[-1] += "."
    elif stage:
        parts.append(f"{subject} is at the '{stage.lower()}' stage of their journey.")
    else:
        parts.append(f"{subject} is still early in their journey, which is completely on track.")

    if milestones:
        parts.append(f"They've already completed {milestones} milestone{'s' if milestones != 1 else ''} along the way.")

    parts.append(
        "Asking what they're enjoying is often more useful than asking how they're "
        "doing — it keeps the conversation in their hands."
    )
    return " ".join(parts)[:MAX_INSIGHT_CHARS]


# --------------------------------------------------------------------------- cache
def _get_cached(db: Session, student_id: int, key: str) -> ParentInsightCache | None:
    row = db.scalar(
        select(ParentInsightCache).where(
            ParentInsightCache.student_id == student_id,
            ParentInsightCache.snapshot_hash == key,
        )
    )
    if row is None:
        return None
    expires = row.expires_at
    if isinstance(expires, datetime) and expires.tzinfo is not None:
        expires = expires.replace(tzinfo=None)
    if expires is not None and expires < datetime.utcnow():
        db.delete(row)
        db.commit()
        return None
    return row


def _store(db: Session, student_id: int, key: str, text: str, source: str) -> None:
    expires = datetime.utcnow() + timedelta(hours=TTL_HOURS)
    existing = db.scalar(
        select(ParentInsightCache).where(
            ParentInsightCache.student_id == student_id,
            ParentInsightCache.snapshot_hash == key,
        )
    )
    if existing is not None:
        existing.insight = text
        existing.source = source
        existing.expires_at = expires
    else:
        db.add(
            ParentInsightCache(
                student_id=student_id,
                snapshot_hash=key,
                insight=text,
                source=source,
                expires_at=expires,
            )
        )
    db.commit()


def purge_expired(db: Session) -> int:
    """Housekeeping. Safe to call anytime; expired rows can never be served."""
    result = db.execute(delete(ParentInsightCache).where(ParentInsightCache.expires_at < datetime.utcnow()))
    db.commit()
    return int(result.rowcount or 0)


# --------------------------------------------------------------------------- entrypoint
async def insight_for(db: Session, student: User, link: ParentStudentLink) -> str | None:
    """Return the insight note for a parent's Overview card.

    Returns None only when no section is shared (there is genuinely nothing to
    describe). Never raises.
    """
    try:
        snapshot = consented_snapshot(db, student, link)
    except Exception:
        logger.exception("parent insight: snapshot build failed for student %s", student.id)
        return None

    if not any(k in snapshot for k in ("basic", "insights", "growth")):
        return None

    key = snapshot_hash(snapshot)

    # --- cache hit
    try:
        cached = _get_cached(db, student.id, key)
        if cached is not None and cached.insight:
            return cached.insight
    except Exception:
        logger.warning("parent insight: cache read failed for student %s", student.id, exc_info=True)

    # --- LLM
    text: str | None = None
    source = "template"
    try:
        from app.services.providers import gemini

        raw = await gemini.complete(
            prompts.parent_insight_prompt(snapshot),
            system=prompts.PARENT_INSIGHT_SYSTEM,
        )
        cleaned = _clean(raw)
        if cleaned:
            text = cleaned
            source = "llm"
    except Exception:
        # Expected whenever Gemini/Ollama are unavailable -- the dashboard must
        # still render. Never surfaced to the parent as an error.
        logger.info("parent insight: LLM unavailable for student %s, using template", student.id)

    if not text:
        text = template_insight(snapshot)
        source = "template"

    try:
        _store(db, student.id, key, text, source)
    except Exception:
        logger.warning("parent insight: cache write failed for student %s", student.id, exc_info=True)

    return text


def _clean(raw: str | None) -> str | None:
    """Strip model chatter down to the note itself."""
    if not raw:
        return None
    text = raw.strip()
    # Models sometimes wrap the note in quotes or a "Note:" prefix.
    for prefix in ("Note:", "Insight:", "Here is the note:", "Here's the note:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1].strip()
    if not text:
        return None
    return text[:MAX_INSIGHT_CHARS]