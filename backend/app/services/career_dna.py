import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.career_dna import CareerDNA
from app.models.user import User
from app.llm import prompts
from app.schemas.career_dna import CareerDNAUpdate, ReflectionUpdate
from app.services.providers import dna_dict, gemini, memory
from app.services.student_context import load_student_context

_NEGATION_RE = re.compile(
    r"\b(?:don'?t\s*(?:not\s+)?like|do\s+not\s+like|not a fan of|not interested in|lost interest in|"
    r"bored of|getting bored of|no longer (?:into|care about)|isn'?t for me|is not for me|"
    r"not into|don'?t care about|don'?t enjoy|hate|can'?t stand|cannot stand|dislike)\b",
    re.I,
)
# "AI is not for me" / "AI isn't for me" — subject comes BEFORE the signal.
_BEFORE_NEGATION_RE = re.compile(
    r"\b([a-z][a-z0-9 &+.+-]{1,24}?)\s+(?:is|was|seems|feels)\s+(?:not\s+)(?:for\s+me|my\s+thing|my\s+jam|my\s+vibe)\b",
    re.I,
)
_PREFER_OVER_RE = re.compile(
    r"\bprefer(?:s|red)?\b[^.]*?\bover\s+([a-z][a-z0-9 &+-]*)", re.I
)
_STOPWORDS = {
    "the", "and", "part", "parts", "when", "that", "with", "this", "too",
    "much", "now", "more", "anymore", "it", "is", "of", "to", "for",
    "on", "in", "my", "me", "i", "a", "an", "stuff", "thing", "things",
    "anymore", "at", "all", "really", "just", "want", "wanna", "going",
    "gonna", "about", "focus", "focusing", "focussing", "only", "so",
    "what", "that", "then", "also", "very", "bit", "little",
}
_FILLER_TAIL_RE = re.compile(
    r"(?:\s+(?:at all|anymore|no more|now|these days|right now|from now on|as much|"
    r"that much|really|at all anymore|now a days|nowadays))\s*$",
    re.I,
)

PREFERENCE_FIELDS = ("interests", "subjects", "skills", "career_zones", "goals", "motivations", "values")


def get_dna(user: User, db: Session) -> CareerDNA | None:
    return db.scalar(select(CareerDNA).where(CareerDNA.user_id == user.id))


def get_or_create_dna(user: User, db: Session) -> CareerDNA:
    dna = get_dna(user, db)
    if dna:
        return dna
    dna = CareerDNA(user_id=user.id)
    db.add(dna)
    db.commit()
    db.refresh(dna)
    return dna


def apply_dna_fields(dna: CareerDNA, data: CareerDNAUpdate) -> None:
    for field in (
        "traits", "motivations", "strengths", "development_areas", "interests",
        "subjects", "skills", "career_zones", "values", "goals", "novi_reflection",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(dna, field, value)
    if data.dna_filled is not None:
        dna.dna_filled = data.dna_filled
    if not dna.dna_filled and any(
        getattr(dna, f) for f in ("traits", "interests", "strengths", "career_zones")
    ):
        dna.dna_filled = True


def update_dna(user: User, data: CareerDNAUpdate, db: Session) -> CareerDNA:
    dna = get_or_create_dna(user, db)
    apply_dna_fields(dna, data)
    db.commit()
    db.refresh(dna)
    _mirror_dna_to_memory(user, dna)
    _rescore_on_dna_change(user, db)
    return dna


def _rescore_on_dna_change(user: User, db: Session) -> None:
    """Keep the stored top career match consistent with the current DNA.

    Runs after any DNA write (chat auto-refresh, manual edit, magic build) so
    the Careers page top pick always matches what the student believes now —
    e.g. "I don't like AI" removes AI as the #1 recommendation immediately.
    """
    from app.services.careers import rescore_matches

    try:
        rescore_matches(db, user, limit=1)
    except Exception as exc:
        print(f"[dna] match rescore skipped: {exc}")


def _mirror_dna_to_memory(user: User, dna: CareerDNA) -> None:
    """Keep Letta's live profile + archival snapshot in sync with Career DNA."""
    if not dna.dna_filled:
        return
    interests = dna.interests or []
    skills = dna.skills or []
    goals = dna.goals or []
    memory.sync_profile(
        user, user.display_name, user.grade, user.school or None,
        interests=interests, skills=skills, goal=goals[0] if goals else None,
    )
    zones = (dna.career_zones or [])[:3]
    if zones:
        memory.archive(
            user,
            f"User's Career DNA shows strongest interest in: {', '.join(zones)}.",
            ("dna", "career_focus"),
        )


async def refresh_dna_from_history(
    user: User, chat_history: list[dict], db: Session, focus: str | None = None,
    conversation_id: int | None = None,
) -> CareerDNA:
    dna = get_or_create_dna(user, db)
    current = dna_dict(dna)
    revoked = revoked_terms(chat_history)
    ctx = load_student_context(db, user)
    student = {
        "name": user.display_name,
        "grade": user.grade,
        "school": user.school,
    }
    student.update(ctx)
    try:
        result = await gemini.complete_json(
            prompts.career_dna_prompt(chat_history, current, student),
            system=prompts.CAREER_DNA_SYSTEM,
        )
        if not isinstance(result, dict) or not any(k in result for k in PREFERENCE_FIELDS):
            raise ValueError("bad shape")
    except Exception as exc:
        raise ValueError("DNA could not be refreshed because the AI service failed. Your saved DNA has been preserved. Please retry.") from exc

    # Deterministic backstop: drop anything the student clearly revoked, even if the LLM
    # forgot to (e.g. "I don't like coding anymore" must remove coding, not keep it).
    cleaned = {field: _clean_list(result.get(field, current.get(field))) for field in PREFERENCE_FIELDS}
    _anchor_context(ctx, cleaned)
    if revoked:
        dna.excluded = _merge_excluded(dna.excluded, revoked)
        for field in PREFERENCE_FIELDS:
            cleaned[field] = prune(cleaned[field], revoked)

    update = CareerDNAUpdate(
        traits=_clean_list(result.get("traits", current.get("traits"))),
        motivations=cleaned["motivations"],
        strengths=_clean_list(result.get("strengths", current.get("strengths"))),
        development_areas=_clean_list(result.get("development_areas", current.get("development_areas"))),
        interests=cleaned["interests"],
        subjects=cleaned["subjects"],
        skills=cleaned["skills"],
        career_zones=cleaned["career_zones"],
        values=cleaned["values"],
        goals=cleaned["goals"],
        novi_reflection=str(result.get("novi_reflection") or ""),
        dna_filled=True,
    )
    apply_dna_fields(dna, update)
    db.commit()
    db.refresh(dna)
    new_dna = dna
    _rescore_on_dna_change(user, db)
    new_dna.sources = build_dna_sources(cleaned, chat_history, conversation_id)
    db.commit()
    db.refresh(new_dna)
    # Memory synchronization must not hold the refresh response open.
    # Chat synchronizes the persisted DNA on its next turn.
    return new_dna


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _msg_mentions(content: str, needle: str) -> bool:
    """Does a user message sound like it mentions this DNA item?

    Tries full-phrase match first, then token overlap, then a fuzzy ratio so
    near-misses ('maths' vs 'math', 'robotics' vs 'robots') still count.
    """
    text = str(content or "").lower()
    if not text:
        return False
    key = _SLUG_RE.sub(" ", needle).strip()
    if not key:
        return False
    if key in text:
        return True
    needle_tokens = [t for t in _SLUG_RE.split(key) if len(t) >= 3]
    if not needle_tokens:
        return False
    msg_tokens = [t for t in _SLUG_RE.split(text) if len(t) >= 3]
    if not msg_tokens:
        return False
    if set(needle_tokens) & set(msg_tokens):
        return True
    for nt in needle_tokens:
        if any(SequenceMatcher(None, nt, mt).ratio() >= 0.82 for mt in msg_tokens):
            return True
    return False


def build_dna_sources(
    cleaned: dict, chat_history: list[dict], conversation_id: int | None = None
) -> dict:
    """Map each DNA field back to the conversation message(s) it came from.

    Deterministic evidence: for every DNA item, find the closest USER message
    in the given history that mentions it, so the My DNA UI can honestly say
    'Novi learned this from your chat'.
    """
    user_msgs = [m for m in chat_history if m.get("role") == "user"]
    sources: dict = {}
    for field, items in cleaned.items():
        if not items:
            continue
        entries = []
        for it in items:
            needle = str(it).lower().strip()
            quote = None
            conv_id = conversation_id
            if len(needle) >= 2:
                for m in reversed(user_msgs):  # nearest message wins
                    content = str(m.get("content") or "")
                    if _msg_mentions(content, needle):
                        quote = content.strip()
                        conv_id = m.get("conversation_id") or conversation_id
                        break
            entries.append({
                "value": it,
                "quote": quote,
                "conversation_id": conv_id,
            })
        sources[field] = entries
    return sources


async def build_dna_from_text(user: User, text: str, db: Session) -> CareerDNA:
    """One-shot DNA build from a student's own words (no chat history needed)."""
    dna = get_or_create_dna(user, db)
    current = dna_dict(dna)
    ctx = load_student_context(db, user)
    student = {
        "name": user.display_name,
        "grade": user.grade,
        "school": user.school,
    }
    student.update(ctx)
    try:
        result = await gemini.complete_json(
            prompts.dna_from_text_prompt(text, current, student),
            system=prompts.CAREER_DNA_SYSTEM,
        )
        if not isinstance(result, dict) or not any(k in result for k in PREFERENCE_FIELDS):
            raise ValueError("bad shape")
    except Exception as exc:
        print(f"[dna] magic build failed: {exc}")
        raise ValueError("Novi couldn't read that just yet — try telling her a little more") from exc

    cleaned = {field: _clean_list(result.get(field, current.get(field))) for field in PREFERENCE_FIELDS}
    _anchor_context(ctx, cleaned)
    update = CareerDNAUpdate(
        traits=_clean_list(result.get("traits", current.get("traits"))),
        motivations=cleaned["motivations"],
        strengths=_clean_list(result.get("strengths", current.get("strengths"))),
        development_areas=_clean_list(result.get("development_areas", current.get("development_areas"))),
        interests=cleaned["interests"],
        subjects=cleaned["subjects"],
        skills=cleaned["skills"],
        career_zones=cleaned["career_zones"],
        values=cleaned["values"],
        goals=cleaned["goals"],
        novi_reflection=str(result.get("novi_reflection") or ""),
        dna_filled=True,
    )
    apply_dna_fields(dna, update)
    db.commit()
    db.refresh(dna)
    new_dna = dna
    _rescore_on_dna_change(user, db)
    new_dna.sources = build_dna_sources(
        cleaned, [{"role": "user", "content": text}], conversation_id=None
    )
    db.commit()
    db.refresh(new_dna)
    # Memory synchronization must not hold the refresh response open.
    # Chat synchronizes the persisted DNA on its next turn.
    return new_dna


def revoked_terms(chat_history: list[dict]) -> list[str]:
    """Extract topics the student has clearly moved away from (as lowercase phrases)."""
    terms: list[str] = []
    for m in chat_history:
        if m.get("role") != "user":
            continue
        text = str(m.get("content") or "")
        text = re.sub(r"\bdon\s+not\s+like\b", "don't like", text, flags=re.I)
        for match in _NEGATION_RE.finditer(text):
            subject = _subject(text[match.end() :].split(), negative=True)
            if subject:
                terms.append(subject)
        for match in _BEFORE_NEGATION_RE.finditer(text):
            subject = _subject(match.group(1).split(), negative=True)
            if subject:
                terms.append(subject)
        for match in _PREFER_OVER_RE.finditer(text):
            subject = _subject(match.group(1).split(), negative=False)
            if subject:
                terms.append(subject)
    return list(dict.fromkeys(t.lower() for t in terms if t))


def _subject(words: list[str], negative: bool = True) -> str:
    """First meaningful topic after a signal phrase.

    Accepts 2-letter acronyms ('AI' -> 'ai'), tolerates 'don not' typos, and
    drops trailing filler like 'anymore' / 'now' / 'at all' that otherwise
    get mistaken for the actual subject.
    """
    cleaned = []
    for w in words:
        t = w.lower().strip("'\".,!?;:")
        if not t:
            continue
        t = t.replace("don not", "").replace("do not", "").strip()
        if not t:
            continue
        cleaned.append(t)
    if not cleaned:
        return ""
    start = 0
    while start < len(cleaned) and cleaned[start] in _STOPWORDS:
        start += 1
    if start >= len(cleaned):
        return ""
    pair = [cleaned[start]]
    for j in range(start + 1, len(cleaned)):
        if len(cleaned[j]) < 2 or cleaned[j].lower() in _STOPWORDS:
            break
        pair.append(cleaned[j])
        break
    return " ".join(pair[:2])


def prune(items: list[str], revoked: list[str]) -> list[str]:
    """Remove any item that contains a revoked topic (e.g. 'coding' in 'competitive coding')."""
    tokens = [re.escape(t) for phrase in revoked for t in phrase.split() if len(t) >= 2]
    if not tokens:
        return items
    pattern = re.compile("|".join(tokens), re.I)
    return [it for it in items if not pattern.search(it.lower())]


def _merge_excluded(existing: list | None, revoked: list[str]) -> list[str]:
    """Persist revoked topics on the DNA, merged and deduped (case-insensitive)."""
    seen: set[str] = set()
    merged: list[str] = []
    for phrase in list(existing or []) + list(revoked or []):
        key = phrase.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(phrase.strip())
    return merged


def _archive_shift(user: User, was: dict, now: CareerDNA) -> None:
    """When the student genuinely swaps one focus for another, record it for the mentor."""
    removed: list[str] = []
    added: list[str] = []
    for field in ("interests", "skills", "career_zones", "goals"):
        old = {x.lower() for x in (was.get(field) or [])}
        new = {x.lower() for x in (getattr(now, field) or [])}
        removed.extend([x for x in old - new if x not in removed])
        added.extend([x for x in new - old if x not in added])
    if not removed or not added:
        return
    try:
        memory.archive(
            user,
            f"User shifted their focus: moved away from {', '.join(removed[:3])} "
            f"toward {', '.join(added[:3])}.",
            ("dna", "shift"),
        )
    except Exception as exc:
        print(f"[dna] shift memory archive failed: {exc}")


def seed_dna_from_context(user: User, db: Session, chat_history: list[dict] | None = None) -> CareerDNA:
    """Deterministically build the Career DNA from what onboarding captured
    (student context), with no LLM round-trip.

    Called immediately after onboarding so the DNA is populated the moment the
    flow finishes; the LLM-based `refresh_dna_from_history` then refines it in
    the background without ever leaving the DNA empty.
    """
    dna = get_or_create_dna(user, db)
    cleaned = {field: _clean_list(dna_dict(dna).get(field)) for field in PREFERENCE_FIELDS}
    ctx = load_student_context(db, user)
    _anchor_context(ctx, cleaned)
    for field in PREFERENCE_FIELDS:
        setattr(dna, field, cleaned[field])
    dna.strengths = _uniq(_clean_list(dna.strengths) + _clean_list(ctx.get("strengths")))
    dna.traits = _uniq(_clean_list(dna.traits) + _clean_list(ctx.get("interests")))
    cleaned["strengths"] = dna.strengths
    _populated_filled(cleaned, dna)
    dna.sources = build_dna_sources(cleaned, chat_history or [], None)
    db.commit()
    db.refresh(dna)
    _rescore_on_dna_change(user, db)
    return dna


def _clean_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _uniq(values: list) -> list:
    """Ordered de-dup of a list of non-empty strings."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        key = str(value).strip()
        if key and key.casefold() not in seen:
            seen.add(key.casefold())
            out.append(key)
    return out


def _populated_filled(cleaned: dict, dna: CareerDNA) -> None:
    """Mark a deterministically-built DNA as filled when it actually has content."""
    if not dna.dna_filled:
        has_content = any(
            _clean_list(cleaned.get(f))
            for f in ("interests", "strengths", "subjects", "skills", "career_zones", "motivations", "goals")
        )
        if has_content:
            dna.dna_filled = True


def _anchor_context(ctx: dict, cleaned: dict) -> dict:
    """Deterministically ground the DNA in what onboarding explicitly captured.

    Merges the student's own answers (enjoyed/difficult subjects, strengths,
    activities, motivators, a self-declared career, a stated life goal) into the
    LLM output so downstream matching can always see them — the LLM stays the
    primary author, this only guarantees the explicit answers survive.
    """
    anchors = {
        "subjects": ctx.get("subjects_enjoyed") or [],
        "strengths": ctx.get("strengths") or [],
        "interests": ctx.get("interests") or [],
        "motivations": ctx.get("motivators") or [],
        "goals": ctx.get("goals") or [],
    }
    from app.services.student_context import career_in_mind_phrase

    career = career_in_mind_phrase(ctx)
    if career:
        anchors["career_zones"] = [career]
    anchors["values"] = list(ctx.get("motivators") or [])

    for field, explicit in anchors.items():
        current = _clean_list(cleaned.get(field))
        merged = list(current)
        for item in explicit:
            key = str(item).strip().lower()
            if key and key not in {str(x).strip().lower() for x in merged}:
                merged.append(str(item).strip())
        cleaned[field] = merged
    return cleaned


def reflect_dna(user: User, data: ReflectionUpdate, db: Session) -> CareerDNA:
    """Handle the 'Yes, that's me' / 'Not quite' feedback on Novi's reflection."""
    dna = get_or_create_dna(user, db)
    if data.accepted:
        dna.dna_filled = True
        db.commit()
        db.refresh(dna)
        try:
            memory.archive(
                user,
                "User confirmed their Career DNA reflection — it feels right.",
                ("dna", "reflection"),
            )
        except Exception as exc:
            print(f"[dna] reflect memory archive failed: {exc}")
    elif data.feedback and data.feedback.strip():
        dna.dna_filled = False
        db.commit()
        db.refresh(dna)
        try:
            memory.archive(
                user,
                f"User refined their Career DNA reflection: {data.feedback.strip()}.",
                ("dna", "reflection"),
            )
        except Exception as exc:
            print(f"[dna] reflect memory archive failed: {exc}")
    return dna


def dna_context(user: User, db: Session, dna: CareerDNA | None = None) -> dict:
    """A compact, current snapshot of the student's DNA used to ground every
    section (careers, universities, roadmap, passport, check-in) in who they are now."""
    dna = dna or get_dna(user, db)
    d = dna_dict(dna)
    zones = d.get("career_zones") or []
    goals = d.get("goals") or []
    interests = d.get("interests") or []
    subjects = d.get("subjects") or []
    skills = d.get("skills") or []
    return {
        "filled": bool(dna and dna.dna_filled),
        "grade": user.grade,
        "label": (zones or interests or [None])[0],
        "top_zone": zones[0] if zones else None,
        "top_goal": goals[0] if goals else None,
        "top_interest": interests[0] if interests else None,
        "top_skill": skills[0] if skills else None,
        "career_zones": zones,
        "goals": goals,
        "interests": interests,
        "subjects": subjects,
        "skills": skills,
    }