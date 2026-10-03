"""Tests for the passport service (CRUD, completion score, chat extraction)."""

import asyncio

import pytest

from app.models.chat import Conversation, Message
from app.models.enums import MessageRole, PassportCategory
from app.models.passport import PassportItem
from app.schemas.passport import PassportItemCreate
from app.services import passport as ps


def _chat_message(db, user, conversation, role: MessageRole, content: str):
    msg = Message(conversation_id=conversation.id, role=role, content=content)
    db.add(msg)
    db.commit()
    return msg


def test_create_item_is_idempotent(db, user):
    data = PassportItemCreate(category="projects", title="Weather app", description="Built with Python")
    first = ps.create_item(db, user, data)
    second = ps.create_item(db, user, data)
    assert first.id == second.id
    assert len(ps.list_items(db, user)) == 1


def test_dedupe_removes_duplicates(db, user):
    for _ in range(2):
        item = PassportItem(user_id=user.id, category=PassportCategory.PROJECTS, title="Same project", description="Same desc")
        db.add(item)
        db.commit()
    removed = ps.dedupe_items(db, user)
    assert removed == 1
    assert len(ps.list_items(db, user)) == 1


def test_completion_scores_and_weakest_category(db, user):
    comp = ps.completion(db, user)
    assert comp["score"] == 0
    assert "projects" in comp["by_category"]
    assert comp["suggested_next"]

    ps.create_item(db, user, PassportItemCreate(category="projects", title="A project"))
    comp2 = ps.completion(db, user)
    assert comp2["score"] > 0


def _mock_json_return(value):
    async def fake_complete_json(prompt, system=None):
        assert system
        return value

    return fake_complete_json


def test_refresh_from_chat_extracts_and_dedupes(db, user, monkeypatch):
    conv = Conversation(user_id=user.id, title="Building stuff")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    _chat_message(db, user, conv, MessageRole.USER, "I built a weather app with python this month")
    _chat_message(db, user, conv, MessageRole.USER, "I won a district science fair last march")
    _chat_message(db, user, conv, MessageRole.USER, "I'm captain of the robotics club now")
    _chat_message(db, user, conv, MessageRole.ASSISTANT, "That's amazing work!")

    monkeypatch.setattr(
        ps.gemini,
        "complete_json",
        _mock_json_return({
            "items": [
                    {"category": "projects", "title": "Weather app", "description": "Built with python", "skills": ["python"], "evidence": "I built a weather app with python"},
                    {"category": "competitions", "title": "District science fair", "description": "Won first place", "date_achieved": "2024-03", "evidence": "I won a district science fair"},
            ]
        }),
    )

    result = asyncio.run(ps.refresh_from_chat(db, user))
    assert result["added"] == 2
    items = ps.list_items(db, user)
    assert {i.title for i in items} == {"Weather app", "District science fair"}

    # A second scan should add nothing new (title-based dedupe).
    result2 = asyncio.run(ps.refresh_from_chat(db, user))
    assert result2["added"] == 0


def test_refresh_from_chat_requires_conversation_depth(db, user):
    result = asyncio.run(ps.refresh_from_chat(db, user))
    assert result["added"] == 0
    assert result["total"] == 0


def test_refresh_rejects_unsupported_ai_claims_from_one_message(db, user, monkeypatch):
    conv = Conversation(user_id=user.id, title="A win")
    db.add(conv)
    db.commit()
    _chat_message(db, user, conv, MessageRole.USER, "I built a small weather app in Python")
    monkeypatch.setattr(ps.gemini, "complete_json", _mock_json_return({"items": [
        {"category": "projects", "title": "Weather app", "evidence": "I built a small weather app in Python", "skills": ["Python", "React"]},
        {"category": "competitions", "title": "Science olympiad", "evidence": "I won a science olympiad"},
    ]}))

    result = asyncio.run(ps.refresh_from_chat(db, user))
    assert result["added"] == 1
    assert result["skipped"] == 1
    item = ps.list_items(db, user)[0]
    assert item.description == "I built a small weather app in Python"
    assert item.skills == ["Python"]
