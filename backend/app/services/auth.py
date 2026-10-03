import hashlib
import hmac
import secrets
from urllib.parse import quote, unquote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    ParentRegisterRequest,
    SignupRequest,
    UserUpdate,
)
from app.services import parent_links
from app.services.providers import memory


async def signup(data: SignupRequest, db: Session) -> User:
    """Student self-registration. Always creates role='student'."""
    existing = db.scalar(select(User).where(User.email == data.email.lower()))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email.lower(),
        password_hash=security.hash_password(data.password),
        # Hard-coded: this route is for students only. Parent accounts are
        # created by register_parent(), which also opens the consent link.
        # SignupRequest rejects role='parent' at validation, so a client cannot
        # reach this branch to escalate.
        role=UserRole.STUDENT,
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

    # A parent may have invited this email before the account existed.
    parent_links.resolve_invitations_for_student(db, user)
    return user


def register_parent(data: ParentRegisterRequest, db: Session) -> tuple[User, "parent_links.ParentStudentLink"]:
    """Self-service parent registration, plus the initial student invitation.

    The role is fixed to PARENT here on the server; a client cannot choose it.
    One email is one role: an existing account of either kind is rejected rather
    than converted.
    """
    email = data.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        if existing.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=400,
                detail="That email is already registered as a student. Sign in as the student instead.",
            )
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=email,
        password_hash=security.hash_password(data.password),
        role=UserRole.PARENT,
        first_name=data.name or data.first_name,
        last_name=data.last_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Parents never get a Letta agent.
    link = parent_links.create_pending_link(db, user, data.student_email)
    return user, link


def login(data: LoginRequest, db: Session) -> User:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not security.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    if data.expected_role and user.role != data.expected_role:
        # Credentials were valid; the caller is simply in the wrong app.
        raise HTTPException(
            status_code=403,
            detail=f"This account is a {user.role} account. Sign in from the {user.role} sign-in page.",
        )

    # First (and every) password login is a chance to claim a pending invitation.
    if user.role == UserRole.STUDENT:
        parent_links.resolve_invitations_for_student(db, user)
    return user


def me(user: User) -> MeResponse:
    """Current identity, always read from the database row rather than the JWT."""
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.display_name,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        role=getattr(user.role, "value", user.role),
        grade=user.grade,
        school=user.school,
        avatar=user.avatar,
        onboarding_completed=user.onboarding_completed,
    )


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


def build_google_authorize_url(state: str, next_path: str, intent: str = "student") -> str:
    """Build Google's consent URL.

    The state is HMAC-signed (see build_oauth_state) and carries the caller's
    ``intent`` -- which app they started from -- so a parent who began in the
    parent flow is not silently created as a student.
    """
    query = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": build_oauth_state(state, next_path, intent),
        "prompt": "select_account",
    })
    return f"{GOOGLE_AUTHORIZE_URL}?{query}"


def _sign(payload: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


def build_oauth_state(nonce: str, next_path: str, intent: str = "student") -> str:
    """nonce:intent:next:sig -- integrity-protected via HMAC on SECRET_KEY.

    The nonce is ALSO stored in an httpOnly cookie for double-submit CSRF
    protection; the signature means a tampered intent/next cannot be injected
    even if the cookie check were bypassed.
    """
    payload = f"{nonce}:{intent}:{quote(next_path, safe='/')}"
    return f"{payload}:{_sign(payload)}"


def verify_oauth_state(state: str) -> tuple[str, str, str] | None:
    """Return (nonce, intent, next_path) if the signature checks out, else None."""
    payload, _, sig = state.rpartition(":")
    if not payload or not sig or not hmac.compare_digest(sig, _sign(payload)):
        return None
    nonce, intent, next_path = payload.split(":", 2)
    return nonce, intent, unquote(next_path)


async def google_login(
    code: str, db: Session, intent: str = "student"
) -> tuple[User, bool]:
    """Exchange a Google authorization code and log the user in (creating them if needed).

    Returns (user, is_new). ``intent`` decides the role of a NEWLY created
    account only -- an existing account is never switched roles by Google sign-in.
    """
    token_payload = await _exchange_google_code(code)
    info = await _verify_google_id_token(token_payload.get("id_token", ""))
    email = (info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google account has no email")
    if str(info.get("email_verified")).lower() not in ("true", "1"):
        raise HTTPException(status_code=401, detail="Google email is not verified")
    return _upsert_google_user(email, info.get("name") or "", info.get("picture"), db, intent)


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


def _upsert_google_user(
    email: str, name: str, picture: str | None, db: Session, intent: str = "student"
) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        if picture and not user.avatar:
            user.avatar = picture
            db.commit()
            db.refresh(user)
        if user.role == UserRole.STUDENT:
            # Google has verified this address, so any outstanding invitation
            # can be attached now.
            parent_links.resolve_invitations_for_student(db, user)
        return user, False

    # One email is one role: only a NEW account may take the requested role.
    role = UserRole.PARENT if intent == "parent" else UserRole.STUDENT
    parts = (name or "").strip().split()
    user = User(
        email=email,
        password_hash=security.hash_password(secrets.token_urlsafe(24)),  # no password login for Google accounts
        role=role,
        first_name=parts[0] if parts else "",
        last_name=" ".join(parts[1:]) if len(parts) > 1 else "",
        avatar=picture or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if role == UserRole.STUDENT:
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

        parent_links.resolve_invitations_for_student(db, user)
    return user, True