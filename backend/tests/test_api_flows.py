"""Check the actual frontend API contracts, with an isolated database."""
from datetime import date
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.router import api_router
from app.core.database import get_db
from app.core.deps import _get_current_user
from app.core.security import hash_password

@pytest.fixture()
def client(db, user):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[_get_current_user] = lambda: user
    return TestClient(app)

@pytest.mark.parametrize('path', [
    '/auth/me', '/auth/links', '/dna', '/dna/context', '/dna/snapshots',
    '/careers', '/careers/categories', '/careers/matches',
    '/universities', '/universities/filters', '/universities/recommended',
    '/roadmap', '/roadmap/goals', '/roadmap/tasks', '/roadmap/priorities',
    '/passport', '/passport/completion', '/checkins', '/checkins/current',
    '/checkins/graph', '/checkins/planner/day', '/chat/conversations', '/dashboard',
])
def test_student_page_reads(client, path):
    response = client.get('/api/v1' + path)
    assert response.status_code == 200, response.text


def test_planner_buttons(client):
    base = '/api/v1/checkins/planner'
    created = client.post(base + '/blocks', json={'date': date.today().isoformat(), 'title': 'Study Python', 'minutes': 30})
    assert created.status_code == 200, created.text
    block = created.json()
    assert client.patch(f"{base}/blocks/{block['id']}").json()['completed'] is True
    saved = client.post(base + '/day/checkin', json={'focus': 'Python', 'mood': 'good', 'energy': 7})
    assert saved.status_code == 200, saved.text
    assert saved.json()['checkin']['focus'] == 'Python'
    assert client.post(base + '/day/auto-plan').status_code == 200
    assert client.delete(f"{base}/blocks/{block['id']}").status_code == 200
    assert client.patch(f"{base}/blocks/{block['id']}").status_code == 404
    assert client.get(base + '/day?date=invalid').status_code == 422


def test_passport_buttons(client):
    created = client.post('/api/v1/passport/items', json={'category': 'projects', 'title': 'Python website'})
    assert created.status_code == 200, created.text
    item_id = created.json()['id']
    assert client.patch(f'/api/v1/passport/items/{item_id}', json={'title': 'Updated website'}).json()['title'] == 'Updated website'
    assert client.delete(f'/api/v1/passport/items/{item_id}').status_code == 200


def test_task_and_goal_buttons(client):
    task = client.post('/api/v1/roadmap/tasks', json={'title': 'Practice Python'}).json()
    assert client.patch(f"/api/v1/roadmap/tasks/{task['id']}", json={'status': 'done'}).json()['status'] == 'done'
    goal = client.post('/api/v1/roadmap/goals', json={'title': 'Build a website'}).json()
    assert client.patch(f"/api/v1/roadmap/goals/{goal['id']}", json={'status': 'done'}).json()['status'] == 'completed'


def test_password_form(client, db, user):
    user.password_hash = hash_password('old-test-password')
    db.commit()
    response = client.post('/api/v1/auth/change-password', json={'current_password': 'old-test-password', 'new_password': 'new-test-password'})
    assert response.status_code == 200, response.text
    assert client.post('/api/v1/auth/change-password', json={'current_password': 'wrong-password', 'new_password': 'new-test-password'}).status_code in (400, 401)


def test_stream_delivers_reply_and_schedules_memory(client, monkeypatch):
    from unittest.mock import AsyncMock
    from app.services import chat
    reply = AsyncMock(return_value={'message': 'Test reply', 'conversation_id': 42, 'message_id': 1, 'used_memory': 'letta'})
    refresh = AsyncMock()
    monkeypatch.setattr(chat, 'handle_message', reply)
    monkeypatch.setattr(chat, 'refresh_after_reply', refresh)
    response = client.post('/api/v1/chat/stream', json={'message': 'Hello'})
    assert response.status_code == 200
    assert 'Test reply' in response.text and '"type": "meta"' in response.text
    assert reply.call_args.kwargs['refresh_memory'] is False
    refresh.assert_awaited_once()


def test_other_student_cannot_change_items(client, db):
    from app.models.user import User
    from app.models.passport import PassportItem
    from app.models.enums import PassportCategory
    other = User(email='other@test.local', password_hash='disabled', first_name='Other')
    db.add(other)
    db.flush()
    item = PassportItem(user_id=other.id, category=PassportCategory.PROJECTS, title='Private project', description='Private')
    db.add(item)
    db.commit()
    assert client.patch(f'/api/v1/passport/items/{item.id}', json={'title': 'Changed'}).status_code == 404
    assert client.delete(f'/api/v1/passport/items/{item.id}').status_code == 404
