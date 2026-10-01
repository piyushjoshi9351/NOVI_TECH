"""Live non-Gemini API verification; creates and removes one test student."""
import sys
import uuid
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import delete
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.core.config import settings

with SessionLocal() as db:
    user = User(email=f'app-smoke-{uuid.uuid4().hex}@example.invalid', password_hash=hash_password('temporary-test-password'), first_name='App', last_name='Smoke', grade=10)
    db.add(user)
    db.commit()
    uid = user.id
    token = create_access_token(str(uid), 'student')
    count = 0
    try:
        with httpx.Client(base_url='http://127.0.0.1:3001/api/v1', headers={'Authorization': f'Bearer {token}'}, timeout=60) as client:
            def call(method, path, body=None, expected=200):
                global count
                r = client.request(method, path, json=body)
                assert r.status_code == expected, (path, r.status_code, r.text[:400])
                count += 1
                print(method, path, r.status_code, flush=True)
                return r.json()
            for path in ['/auth/me','/auth/links','/dna','/dna/context','/dna/snapshots','/careers','/careers/categories','/careers/matches','/universities','/universities/filters','/universities/recommended','/roadmap','/roadmap/goals','/roadmap/tasks','/roadmap/priorities','/passport','/passport/completion','/checkins','/checkins/current','/checkins/graph','/checkins/planner/day','/chat/conversations','/dashboard']:
                call('GET',path)
            call('PATCH','/auth/me',{'first_name':'Updated Smoke'})
            call('POST','/auth/change-password',{'current_password':'temporary-test-password','new_password':'changed-test-password'})
            login = call('POST','/auth/login',{'email':user.email,'password':'changed-test-password'})
            assert login['access_token']
            item = call('POST','/passport/items',{'category':'projects','title':'Test Python website'})
            call('PATCH',f"/passport/items/{item['id']}",{'description':'Built for the smoke test'})
            call('DELETE',f"/passport/items/{item['id']}")
            task = call('POST','/roadmap/tasks',{'title':'Test task'})
            call('PATCH',f"/roadmap/tasks/{task['id']}",{'status':'done'})
            goal = call('POST','/roadmap/goals',{'title':'Test goal'})
            call('PATCH',f"/roadmap/goals/{goal['id']}",{'status':'done'})
            block = call('POST','/checkins/planner/blocks',{'date':date.today().isoformat(),'title':'Test study block','minutes':30})
            call('PATCH',f"/checkins/planner/blocks/{block['id']}")
            call('POST','/checkins/planner/day/checkin',{'focus':'Testing','mood':'good','energy':8})
            call('POST','/checkins/planner/day/auto-plan')
            call('DELETE',f"/checkins/planner/blocks/{block['id']}")
            snapshots=call('POST','/dna/snapshots',{'label':'Test snapshot'})
            call('PATCH',f"/dna/snapshots/{snapshots[0]['id']}",{'label':'Updated snapshot'})
            call('DELETE',f"/dna/snapshots/{snapshots[0]['id']}")
            call('GET','/onboarding/state')
            db.refresh(user)
            assert user.letta_agent_id, 'Onboarding did not provision a Letta agent'
            print('Onboarding agent provisioned; total checks:',count,flush=True)
    finally:
        db.rollback()
        db.refresh(user)
        if user.letta_agent_id:
            headers={'Authorization':f'Bearer {settings.LETTA_API_KEY}'} if settings.LETTA_API_KEY else {}
            response=httpx.delete(f'{settings.LETTA_BASE_URL.rstrip("/")}/v1/agents/{user.letta_agent_id}',headers=headers,timeout=30)
            response.raise_for_status()
        db.execute(delete(User).where(User.id == uid))
        db.commit()
