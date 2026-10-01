import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message
from app.models.enums import MessageRole
from app.models.user import User, UserRole
from app.llm import prompts
from app.services import state_sync
from app.services.career_dna import get_dna
from app.services.providers import gemini, memory


def _lazy_ensure_agent(user: User, db: Session) -> str | None:
    """Provision a Letta agent for a student on first use if it hasn't been created."""
    if user.letta_agent_id:
        try:
            if memory.letta.agent_exists(user.letta_agent_id):
                return user.letta_agent_id
        except Exception:
            return user.letta_agent_id
        # Recreate only when Letta explicitly confirms the saved agent is gone.
    if user.role != UserRole.STUDENT or not memory.is_reachable():
        return None
    agent_id = memory.ensure_agent(
        user_id=user.id,
        name=user.display_name,
        grade=user.grade,
        school=user.school or None,
        existing=None,
    )
    if agent_id:
        user.letta_agent_id = agent_id
        db.commit()
    return agent_id


def _student_profile_parts(user: User, db: Session) -> dict:
    """The atomic profile fields used to seed/seal Letta memory."""
    dna = get_dna(user, db)
    return {
        "name": user.display_name,
        "grade": user.grade,
        "school": user.school or None,
        "interests": (dna.interests if dna else []) or [],
        "skills": (dna.skills if dna else []) or [],
        "goal": ((dna.goals[0] if dna.goals else None) if dna else None),
    }


async def handle_message(user: User, message: str, conversation_id: int | None, db: Session, refresh_memory: bool = True) -> dict:
    """Send a message and produce the reply through the memory-aware pipeline."""
    conversation = get_or_create_conversation(user, conversation_id, message, db)

    db.add(Message(conversation_id=conversation.id, role=MessageRole.USER, content=message))
    db.commit()

    response, source = await _generate_reply(user, message, conversation.id, db)

    ai_message = Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content=response)
    db.add(ai_message)
    db.commit()
    db.refresh(ai_message)

    conversation.title = conversation.title or _make_title(message)
    db.commit()

    if refresh_memory:
        await _refresh_memory_and_dna(user, conversation.id, response, db)

    return {
        "message": response,
        "conversation_id": conversation.id,
        "message_id": ai_message.id,
        "used_memory": source,
    }


def get_or_create_conversation(
    user: User, conversation_id: int | None, first_message: str, db: Session
) -> Conversation:
    if conversation_id:
        conversation = db.get(Conversation, conversation_id)
        if conversation and conversation.user_id == user.id:
            return conversation
    conversation = Conversation(user_id=user.id, title=_make_title(first_message))
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(user: User, db: Session) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(db.scalars(stmt))


def list_messages(user: User, conversation_id: int, db: Session) -> list[Message]:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        return []
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(db.scalars(stmt))


def get_chat_history(user: User, conversation_id: int, db: Session) -> list[dict]:
    return [
        {"role": m.role.value, "content": m.content}
        for m in list_messages(user, conversation_id, db)
    ]


# --------------------------------------------------------------------------- internals
async def _generate_reply(user: User, message: str, conversation_id: int, db: Session) -> tuple[str, str]:
    agent_id = _lazy_ensure_agent(user, db)
    # Pages -> chat: mirror the freshest DB state into Letta's memory so the
    # next reply is grounded in the student's actual roadmap/passport/tasks.
    await _push_state_to_memory(user, db)

    if agent_id and memory.is_reachable():
        try:
            reply = await asyncio.wait_for(
                asyncio.to_thread(memory.chat, agent_id, message, user),
                timeout=90.0,
            )
            if reply:
                return reply, "letta"
        except Exception as exc:
            print(f"[chat] letta failed, falling back to gemini: {exc}")

    # Gemini fallback
    context = await _gemini_memory_context(user, db)
    try:
        response = await gemini.complete(
            prompts.chat_prompt(message, _user_context(user)),
            system=prompts.chat_system(context),
        )
        return response, "gemini"
    except Exception as exc:
        return f"I hit a small snag reaching my brain. Give me a few minutes and try again? ({exc})", "gemini"


async def _gemini_memory_context(user: User, db: Session) -> str:
    parts = []
    recent = list(db.scalars(
        select(Message).join(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(12)
    ))
    if recent:
        parts.append("Recent conversation:\n" + "\n".join(
            f"{m.role.value}: {m.content[:800]}" for m in reversed(recent)
        ))

    # Synced app state (goals, roadmap %, priorities, tasks, passport)
    try:
        state = state_sync.build_snapshot(user, db)
        if state:
            parts.append(state)
    except Exception as exc:
        print(f"[chat] state context skipped: {exc}")

    if user.letta_agent_id and memory.is_reachable():
        try:
            profile = await asyncio.to_thread(memory.current_profile, user.letta_agent_id)
            if profile:
                parts.append(profile)
            latest_message = recent[0].content if recent else ""
            recalled = await asyncio.to_thread(memory.recall_context, user.letta_agent_id, latest_message)
            if recalled:
                parts.append(recalled[:6000])
        except Exception:
            pass
    dna = get_dna(user, db)
    if dna and dna.dna_filled:
        bits = []
        if dna.interests:
            bits.append("Interests: " + ", ".join(dna.interests))
        if dna.career_zones:
            bits.append("Career zones: " + ", ".join(dna.career_zones))
        if dna.goals:
            bits.append("Goals: " + ", ".join(dna.goals))
        parts.extend(bits)
    return "\n".join(parts)


async def _refresh_memory_and_dna(user: User, conversation_id: int, reply: str, db: Session) -> None:
    chat_history = get_chat_history(user, conversation_id, db)
    agent_id = _lazy_ensure_agent(user, db)

    if agent_id and memory.is_reachable():
        try:
            await asyncio.to_thread(memory.seed_profile, agent_id, **_student_profile_parts(user, db))
        except Exception as exc:
            print(f"[chat] memory seed skipped: {exc}")
        try:
            await memory.update_profile_from_chat(
                agent_id, chat_history, _user_context(user)
            )
        except Exception as exc:
            print(f"[chat] profile update skipped: {exc}")
        try:
            await memory.store_facts(agent_id, chat_history, user.grade)
        except Exception as exc:
            print(f"[chat] fact storage skipped: {exc}")

    # Refresh Career DNA every 3 messages from the current conversation
    if len(chat_history) % 3 == 0:
        try:
            await _auto_refresh_dna(user, conversation_id, db)
        except Exception as exc:
            print(f"[chat] dna refresh skipped: {exc}")

    # Chat -> pages: re-mirror the DB (DNA may have changed above) into Letta memory.
    try:
        await _push_state_to_memory(user, db)
    except Exception as exc:
        print(f"[chat] state re-sync skipped: {exc}")


async def _auto_refresh_dna(user: User, conversation_id: int, db: Session) -> None:
    from app.services.career_dna import refresh_dna_from_history

    chat_history = get_chat_history(user, conversation_id, db)
    if len(chat_history) < 2:
        return
    await refresh_dna_from_history(user, chat_history, db, conversation_id=conversation_id)


async def _push_state_to_memory(user: User, db: Session) -> bool:
    agent = getattr(user, "letta_agent_id", None)
    if not agent or not memory.is_reachable():
        return False
    text = state_sync.build_snapshot(user, db)
    if not text:
        return False
    return await asyncio.to_thread(memory.set_state, agent, text, getattr(user, "grade", None))


def _user_context(user: User) -> dict:
    return {
        "name": user.display_name,
        "grade": user.grade,
        "school": user.school,
        "email": user.email,
    }


def _make_title(message: str) -> str:
    return message.strip()[:60] or f"Chat {uuid.uuid4().hex[:6]}"


async def refresh_after_reply(user_id: int, conversation_id: int, reply: str) -> None:
    """Use a separate session after the response has been delivered."""
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            return
        try:
            await _refresh_memory_and_dna(user, conversation_id, reply, db)
        except Exception as exc:
            db.rollback()
            print(f"[chat] background memory update failed: {exc}")
