import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.services import auth as auth_service

logger = logging.getLogger("novi.google_auth")

router = APIRouter(tags=["auth"])


@router.get("/auth/google", include_in_schema=False)
async def google_oauth_start(next: str = "/login", intent: str = "student"):
    """Redirect the browser to Google's consent screen.

    `next` is the frontend route (/login or /signup) the user returns to.
    `intent` ("student" | "parent") records which app they started in so a new
    account is created with the right role. It is HMAC-signed into `state`.

    A CSRF nonce is stored in an httpOnly cookie AND echoed in the OAuth `state`.
    """
    if not auth_service.google_is_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    if not _safe_next(next):
        next = "/login"
    if intent not in ("student", "parent"):
        intent = "student"

    nonce = secrets.token_urlsafe(32)
    url = auth_service.build_google_authorize_url(nonce, next, intent)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "google_oauth_state",
        nonce,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=True,   # required for the cookie to survive the HTTPS Render→Google→Render round-trip
    )
    return response


@router.get("/auth/google/callback", include_in_schema=False)
async def google_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Exchange the Google code, log the user in, and bounce them back to the frontend."""
    # Google itself can return ?error=access_denied (or similar) instead of ?code=.
    # Treat it as a user-cancelled flow, not a server error.
    if error:
        logger.info("Google OAuth returned an error response: %s", error)
        return _google_fail(request, detail="google_oauth_cancelled")

    if not auth_service.google_is_configured():
        logger.error(
            "Google OAuth callback reached but OAuth is not configured. "
            "Ensure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI "
            "are set as environment variables on Render."
        )
        return _google_fail(request, detail="google_oauth_requires_code")

    if not code or not state:
        logger.warning(
            "Google OAuth callback missing required params: code=%s state=%s",
            bool(code),
            bool(state),
        )
        return _google_fail(request, detail="google_oauth_requires_code")

    expected = request.cookies.get("google_oauth_state")
    if not expected:
        return _google_fail(request, detail="google_oauth_expired")

    verified = auth_service.verify_oauth_state(state)
    if verified is None:
        logger.warning("google OAuth state signature invalid")
        return _google_fail(request, detail="google_oauth_verification_failed")

    csrf, intent, next_path = verified
    if not _safe_next(next_path):
        next_path = "/login"
    if not hmac.compare_digest(csrf, expected):
        logger.warning("google OAuth state mismatch (CSRF guard) for path %s", next_path)
        return _google_fail(request, detail="google_oauth_verification_failed")
    if intent not in ("student", "parent"):
        intent = "student"

    try:
        user, is_new = await auth_service.google_login(code, db, intent)
    except HTTPException as exc:
        logger.warning("google login rejected: %s", exc.detail)
        return _google_fail(request, detail="google_oauth_rejected")
    except Exception:
        logger.exception("google login failed unexpectedly", exc_info=True)
        return _google_fail(request, detail="google_oauth_failed")

    role = getattr(user.role, "value", user.role)
    token = security.create_access_token(str(user.id), str(role))
    dest = f"{settings.FRONTEND_URL.rstrip('/')}{next_path}?google_token={token}&google_new={'1' if is_new else '0'}"
    response = RedirectResponse(dest, status_code=302)
    response.delete_cookie("google_oauth_state")
    return response


def _safe_next(path: str) -> bool:
    return bool(path) and path.startswith("/") and not path.startswith("//") and ".." not in path


def _google_fail(request: Request, detail: str = "google_oauth_failed") -> RedirectResponse:
    response = RedirectResponse(
        f"{settings.FRONTEND_URL.rstrip('/')}/login?google_error={detail}",
        status_code=302,
    )
    if request.cookies.get("google_oauth_state"):
        response.delete_cookie("google_oauth_state")
    return response