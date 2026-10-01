"""Exercise live refresh and advice via the frontend proxy using a temporary student."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import time
import uuid
import httpx
from sqlalchemy import delete
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User
from app.models.chat import Conversation, Message
from app.models.enums import MessageRole

with SessionLocal() as db:
    user = User(email=f'refresh-smoke-{uuid.uuid4().hex}@example.invalid', password_hash='disabled-test-login', first_name='Smoke', last_name='Test', grade=10)
    db.add(user)
    db.commit()
    uid = user.id
    conv = Conversation(user_id=uid, title='Temporary refresh verification')
    db.add(conv)
    db.commit()
    db.add(Message(conversation_id=conv.id, role=MessageRole.USER, content='I enjoy computer science and Python programming. I built a Python website. I want to become a software engineer. I dislike automotive repair.'))
    db.commit()
    token = create_access_token(str(uid), 'student')
    try:
        with httpx.Client(base_url='http://127.0.0.1:3001/api/v1', headers={'Authorization': f'Bearer {token}'}, timeout=110) as client:
            for method, path, body in [('POST','/dna/refresh',None), ('GET','/dna',None), ('GET','/dna/snapshots',None), ('POST','/careers/match',{'limit': 5})]:
                start=time.monotonic()
                r=client.request(method,path,json=body)
                print(path,r.status_code,round(time.monotonic()-start,1),'seconds',flush=True)
                r.raise_for_status()
                data=r.json()
                if path == '/dna/refresh':
                    assert data['dna_filled'] and data['interests'], data
                    print('DNA interests:', data['interests'],flush=True)
                if path == '/careers/match':
                    print('Top matches:', [m['career']['title'] for m in data],flush=True)
                    assert data
                    slug=data[0]['career']['slug']
            for path, method, body in [(f'/careers/{slug}/advice','GET',None),('/universities/advice','POST',{'question':'Which computer science program should I explore and which details must I verify?', 'subject':'computer-science'})]:
                start=time.monotonic()
                r=client.request(method,path,json=body)
                print(path,r.status_code,round(time.monotonic()-start,1),'seconds',flush=True)
                r.raise_for_status()
                data=r.json()
                assert data.get('fit_statement') or data.get('answer'), data
                print('Nonempty AI answer verified',flush=True)
    finally:
        db.rollback()
        db.execute(delete(User).where(User.id == uid))
        db.commit()
