import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.services import career_dna, careers


def test_refresh_failure_preserves_dna(db, user, monkeypatch):
    dna = career_dna.get_or_create_dna(user, db)
    dna.interests = ['music']
    db.commit()
    monkeypatch.setattr(career_dna.gemini, 'complete_json', AsyncMock(side_effect=RuntimeError('offline')))
    with pytest.raises(ValueError, match='preserved'):
        asyncio.run(career_dna.refresh_dna_from_history(user, [{'role': 'user', 'content': 'I like art'}], db))
    db.refresh(dna)
    assert dna.interests == ['music']


def test_refresh_does_not_restore_revoked_onboarding(db, user, monkeypatch):
    monkeypatch.setattr(career_dna, 'load_student_context', lambda *a: {'interests': ['coding']})
    monkeypatch.setattr(career_dna.gemini, 'complete_json', AsyncMock(return_value={'interests': ['music']}))
    dna = asyncio.run(career_dna.refresh_dna_from_history(user, [{'role': 'user', 'content': 'I dislike coding. I like music.'}], db))
    assert 'coding' not in dna.interests
    assert 'music' in dna.interests


def test_positive_preference_is_not_revoked():
    assert career_dna.revoked_terms([{'role': 'user', 'content': 'AI is for me'}]) == []


def test_matching_requires_meaningful_words():
    assert not careers._contains('AI', 'repair and maintenance')
    assert not careers._contains('I want to become a software engineer', 'work in mechanical engineering')
    assert careers._contains('software engineer', 'software engineer building applications')


def test_snapshot_routes_and_ownership(db, user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.career_dna import router
    from app.core.database import get_db
    from app.core.deps import get_current_student
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_student] = lambda: user
    client = TestClient(app)
    assert client.get('/dna/snapshots').json() == []
    response = client.post('/dna/snapshots', json={'label': 'Test DNA'})
    assert response.status_code == 200
    assert response.json()[0]['label'] == 'Test DNA'
    assert client.patch('/dna/snapshots/999999', json={'label': 'Missing'}).status_code == 404


def test_missing_agent_is_recreated(db, user, monkeypatch):
    from app.services import chat
    user.letta_agent_id = 'missing-agent'
    db.commit()
    monkeypatch.setattr(chat.memory.letta, 'agent_exists', lambda _: False)
    monkeypatch.setattr(chat.memory, 'is_reachable', lambda: True)
    monkeypatch.setattr(chat.memory, 'ensure_agent', lambda **kwargs: 'replacement-agent')
    assert chat._lazy_ensure_agent(user, db) == 'replacement-agent'
    db.refresh(user)
    assert user.letta_agent_id == 'replacement-agent'
