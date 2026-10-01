import secrets
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    UserUpdate,
    validate_image_data_url,
)
from app.services.providers import memory


def _clean_link(link: dict) -> dict:
    """Keep only a trimmed label + http(s) URL, so the profile can't inject
    javascript: URLs or unbounded junk into every page that renders it."""
    label = str(link.get("label", "")).strip()[:60]
    url = str(link.get("url", "")).strip()
    if url and not url.lower().startswith(("http://", "https://")):
        url = ""
    return {"label": label, "url": url[:500]}


async def signup(data: SignupRequest, db: Session) -> User:
    existing = db.scalar(select(User).where(User.email == data.email.lower()))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email.lower(),
        password_hash=security.hash_password(data.password),
        role=UserRole(data.role) if data.role in ("student", "parent") else UserRole.STUDENT,
        first_name=data.name or data.first_name,
        last_name=data.last_name,
        grade=data.grade,
        school=data.school,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if user.role == UserRole.STUDENT:
        try:
            agent_id = memory.ensure_agent(
                user_id=user.id, name=user.display_name, grade=user.grade,
                school=user.school or None, existing=None,
            )
            if agent_id:
                user.letta_agent_id = agent_id
                db.commit()
        except Exception as exc:
            print(f"[auth] agent creation skipped: {exc}")
    return user


def login(data: LoginRequest, db: Session) -> User:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not security.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return user


def update_profile(user: User, data: UserUpdate, db: Session) -> User:
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.grade is not None:
        user.grade = data.grade
    if data.school is not None:
        user.school = data.school
    if data.avatar is not None:
        user.avatar = data.avatar or None
    # "" clears a field; None means "leave it alone", so the editor can save one
    # field without wiping the others.
    for field in ("headline", "location", "about_me"):
        value = getattr(data, field, None)
        if value is not None:
            setattr(user, field, value.strip() or None)
    if data.links is not None:
        user.links = [_clean_link(x) for x in data.links] or None
    for field in ("profile_photo", "banner_photo"):
        value = getattr(data, field, None)
        if value is not None:
            setattr(user, field, validate_image_data_url(value, field))
    db.commit()
    db.refresh(user)
    return user


def change_password(user: User, current_password: str, new_password: str, db: Session) -> User:
    if not security.verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = security.hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------- Google OAuth

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def google_is_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI)


def build_google_authorize_url(state: str, next_path: str) -> str:
    query = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": f"{state}:{quote(next_path, safe='/')}",
        "prompt": "select_account",
    })
    return f"{GOOGLE_AUTHORIZE_URL}?{query}"


async def google_login(code: str, db: Session) -> tuple[User, bool]:
    """Exchange a Google authorization code and log the user in (creating them if needed).

    Returns (user, is_new). Confirmed students default to the student role.
    """
    token_payload = await _exchange_google_code(code)
    info = await _verify_google_id_token(token_payload.get("id_token", ""))
    email = (info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google account has no email")
    if str(info.get("email_verified")).lower() not in ("true", "1"):
        raise HTTPException(status_code=401, detail="Google email is not verified")
    return _upsert_google_user(email, info.get("name") or "", info.get("picture"), db)


async def _exchange_google_code(code: str) -> dict:
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google token exchange failed") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Google token exchange failed")
    return resp.json()


async def _verify_google_id_token(id_token: str) -> dict:
    """Validate the Google ID token and return its verified claims (email, name, picture)."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google token verification failed") from exc
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    info = resp.json()
    if info.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google token audience mismatch")
    return info


def _upsert_google_user(email: str, name: str, picture: str | None, db: Session) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        if picture and not user.avatar:
            user.avatar = picture
            db.commit()
            db.refresh(user)
        return user, False

    parts = (name or "").strip().split()
    user = User(
        email=email,
        password_hash=security.hash_password(secrets.token_urlsafe(24)),  # no password login for Google accounts
        role=UserRole.STUDENT,
        first_name=parts[0] if parts else "",
        last_name=" ".join(parts[1:]) if len(parts) > 1 else "",
        avatar=picture or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        agent_id = memory.ensure_agent(
            user_id=user.id, name=user.display_name, grade=user.grade,
            school=user.school or None, existing=None,
        )
        if agent_id:
            user.letta_agent_id = agent_id
            db.commit()
    except Exception as exc:
        print(f"[auth] google agent creation skipped: {exc}")
    return user, True