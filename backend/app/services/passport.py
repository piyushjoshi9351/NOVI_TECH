from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.llm import prompts
from app.models.chat import Conversation, Message
from app.models.enums import MessageRole, PassportCategory
from app.models.passport import PassportItem
from app.models.user import User
from app.schemas.passport import PassportItemCreate, PassportItemUpdate
from app.services.career_dna import get_dna
from app.services.providers import gemini, memory
from app.services.student_context import load_student_context

CORE_CATEGORIES = (
    "projects", "competitions", "certifications", "leadership", "research", "activities",
)
CATEGORY_EMOJI = {
    "projects": "🛠️",
    "competitions": "🏆",
    "certifications": "📜",
    "leadership": "🤝",
    "research": "🔬",
    "activities": "🎭",
    "achievements": "⭐",
}
CATEGORY_DESCRIPTIONS = {
    "projects": "Show what you built.",
    "competitions": "Show what you challenged yourself with.",
    "certifications": "Show what you've learned.",
    "leadership": "Show how you've contributed.",
    "research": "Show how you've explored.",
    "activities": "Show what makes you, you.",
    "achievements": "Show what you've accomplished.",
}


def list_items(db: Session, user: User, category: str | None = None) -> list[PassportItem]:
    stmt = select(PassportItem).where(PassportItem.user_id == user.id).order_by(PassportItem.created_at.desc())
    if category:
        stmt = stmt.where(PassportItem.category == category)
    return list(db.scalars(stmt))


def create_item(db: Session, user: User, data: PassportItemCreate) -> PassportItem:
    dup = db.scalar(
        select(PassportItem).where(
            PassportItem.user_id == user.id,
            PassportItem.category == data.category,
            func.lower(PassportItem.title) == data.title.strip().lower(),
            func.lower(func.coalesce(PassportItem.description, ""))
            == (data.description or "").strip().lower(),
        )
    )
    if dup:
        return dup  # idempotent: identical entries are not duplicated

    item = PassportItem(
        user_id=user.id,
        category=PassportCategory(data.category),
        title=data.title.strip(),
        description=(data.description or "").strip(),
        skills=data.skills,
        date_achieved=data.date_achieved,
        certificate_url=data.certificate_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    memory.archive(
        user,
        f"User added to their passport ({item.category.value}): {item.title}.",
        ("passport", item.category.value),
    )
    return item


def dedupe_items(db: Session, user: User) -> int:
    """Merge duplicate passport entries (same category + title + description).

    Keeps the earliest verified/created item, deletes the rest. Returns the number removed.
    """
    from collections import defaultdict

    groups: dict[str, list[PassportItem]] = defaultdict(list)
    for item in list_items(db, user):
        key = "|".join(
            str(x).strip().lower()
            for x in (item.category.value, item.title, item.description or "")
        )
        groups[key].append(item)

    removed = 0
    for items in groups.values():
        if len(items) < 2:
            continue
        items.sort(
            key=lambda i: (not i.verified, i.created_at or datetime.min)
        )
        for extra in items[1:]:
            db.delete(extra)
            removed += 1
    if removed:
        db.commit()
    return removed


def update_item(db: Session, user: User, item_id: int, data: PassportItemUpdate) -> PassportItem | None:
    item = db.get(PassportItem, item_id)
    if not item or item.user_id != user.id:
        return None
    for field in ("title", "description", "skills", "date_achieved", "certificate_url", "verified"):
        value = getattr(data, field)
        if value is not None:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    memory.archive(
        user,
        f"User updated a passport item ({item.category.value}): {item.title}.",
        ("passport", item.category.value),
    )
    return item


def delete_item(db: Session, user: User, item_id: int) -> bool:
    item = db.get(PassportItem, item_id)
    if not item or item.user_id != user.id:
        return False
    db.delete(item)
    db.commit()
    return True


def _chat_history(db: Session, user: User) -> list[dict]:
    """All user/assistant messages across the student's conversations, oldest first."""
    stmt = (
        select(Message)
        .join(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Message.created_at.asc())
    )
    return [
        {"role": m.role.value, "content": m.content}
        for m in db.scalars(stmt)
        if m.role != MessageRole.SYSTEM
    ]


async def refresh_from_chat(db: Session, user: User) -> dict:
    """Scan the student's chat history and auto-add new passport entries.

    Returns {"added": int, "skipped": int, "total": int} so the UI can report
    what Novi found. Skips entries that already exist (title-based dedupe).
    """
    history = [m for m in _chat_history(db, user) if m["role"] == MessageRole.USER.value]
    user_msgs = history
    if not user_msgs:
        return {"added": 0, "skipped": 0, "total": len(user_msgs)}

    existing = [i.title for i in list_items(db, user)]
    added = 0
    skipped = 0
    existing_titles = set(t.strip().lower() for t in existing)
    # Process every conversation, in bounded chunks, so an old achievement is
    # still discovered on refresh after the student has chatted many times.
    for start in range(0, len(history), 30):
        chunk = history[start:start + 30]
        if not any(m["role"] == MessageRole.USER.value for m in chunk):
            continue
        try:
            result = await gemini.complete_json(
                prompts.passport_extract_prompt(chunk, list(existing_titles)),
                system=prompts.PASSPORT_EXTRACT_SYSTEM,
            )
        except Exception as exc:
            print(f"[passport] chat extraction failed: {exc}")
            raise RuntimeError("Passport refresh could not reach the AI provider") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Passport refresh returned an invalid AI response")
        for raw in result.get("items") or []:
            if _add_extracted_item(db, user, raw, chunk, existing_titles):
                added += 1
            else:
                skipped += 1
    if added:
        dedupe_items(db, user)
    return {"added": added, "skipped": skipped, "total": len(user_msgs)}


def _add_extracted_item(db: Session, user: User, raw: dict, chunk: list[dict], existing_titles: set[str]) -> bool:
    if not isinstance(raw, dict):
        return False
    category = str(raw.get("category", "")).strip()
    if category not in CORE_CATEGORIES + ("achievements",):
        return False
    title = str(raw.get("title", "")).strip()
    if not title or title.lower() in existing_titles:
        return False
    evidence = str(raw.get("evidence") or "").strip()
    if len(evidence) < 8 or not any(
        evidence.casefold() in m["content"].casefold()
        for m in chunk if m["role"] == MessageRole.USER.value
    ):
        return False
    title_words = {word for word in title.casefold().split() if len(word) > 3}
    if title_words and not any(word in evidence.casefold() for word in title_words):
        return False
    date_str = str(raw.get("date_achieved") or "").strip()
    date_achieved = None
    if date_str[:7].count("-") == 1 and date_str[:7] in evidence:
        try:
            date_achieved = datetime.strptime(date_str[:7], "%Y-%m").date()
        except ValueError:
            date_achieved = None
    data = PassportItemCreate(
        category=category,
        title=title,
        description=evidence,
        skills=[
            str(s).strip()
            for s in (raw.get("skills") or [])
            if str(s).strip() and str(s).casefold() in evidence.casefold()
        ],
        date_achieved=date_achieved,
    )
    created = create_item(db, user, data)
    existing_titles.add(created.title.strip().lower())
    return True


def completion(db: Session, user: User) -> dict:
    items = list_items(db, user)
    counts = {category: sum(1 for i in items if i.category == category) for category in CORE_CATEGORIES}
    achievements = sum(1 for i in items if i.category == PassportCategory.ACHIEVEMENTS)

    points = min(3, counts["projects"]) * 6.0
    points += min(3, counts["competitions"]) * 6.0
    points += min(3, counts["certifications"]) * 6.0
    points += min(3, counts["leadership"]) * 6.0
    points += min(3, counts["research"]) * 6.0
    points += min(3, counts["activities"]) * 6.0
    points += min(2, achievements) * 6.0
    score = round(min(100, points / 1.2))

    by_category = {c: round(min(100, min(3, counts[c]) * 6.0 / 18.0 * 100)) for c in CORE_CATEGORIES}
    covered = [c for c, pct in by_category.items() if pct >= 25]

    weakest = min(CORE_CATEGORIES, key=lambda c: by_category[c])
    dna = get_dna(user, db)
    focus = None
    if dna:
        focus = (dna.career_zones or [None])[0] or (dna.interests or [None])[0]
    if not focus:
        ctx = load_student_context(db, user)
        focus = (
            ctx.get("career_in_mind_phrase")
            or (ctx.get("interests") or [None])[0]
            or (ctx.get("goals") or [None])[0]
        )
    dna_focus = focus or "your strongest career direction"

    if by_category[weakest] == 0:
        suggested_next = f"Add your first {weakest.replace('_', ' ')} item — {CATEGORY_DESCRIPTIONS[weakest]}"
        if focus:
            category_copy = {
                "projects": f"Add your first project — a {focus.lower()} build would prove your DNA in action.",
                "competitions": f"Add your first competition — enter one tied to {focus.lower()}.",
                "certifications": f"Add your first certification — look for one that deepens your {focus.lower()} skills.",
                "leadership": f"Add your first leadership item — something that shows you can drive {focus.lower()} work forward.",
                "research": f"Add your first research item — a small study or analysis in {focus.lower()} counts.",
                "activities": f"Add your first activity — a club or event that connects you to {focus.lower()}.",
            }
            suggested_next = category_copy.get(weakest, suggested_next)
    else:
        suggested_next = f"Deepen your {weakest.replace('_', ' ')} portfolio with one more strong example."

    note = (
        f"Your DNA points most strongly toward {dna_focus.lower()}. The strongest passports "
        "tell one clear story — aim to build projects, competition entries and leadership "
        "evidence around that direction rather than spreading yourself thin."
    )
    return {
        "score": score,
        "by_category": by_category,
        "categories_covered": covered,
        "suggested_next": suggested_next,
        "dna_focus": dna_focus,
        "novi_note": note,
    }
