import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import ORMModel, RoleBase, USER_ROLES
from app.schemas.passwords import ExistingPassword, NewPassword

# Only inline image data URLs are accepted, and only the formats a browser can
# render in an <img>. Anything else (scripts, remote URLs, svg) is rejected.
_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/]+={0,2}$")
MAX_IMAGE_BYTES = 2 * 1024 * 1024   # ~2 MB decoded, before base64 inflation


def validate_image_data_url(value: str | None, field: str) -> str | None:
    """Reject anything that is not a small base64 raster image data URL."""
    if value is None:
        return None
    if value == "":
        return None
    if not _DATA_URL.match(value):
        raise HTTPException(status_code=422, detail=f"{field} must be a base64 image data URL (png, jpeg, gif or webp)")
    # 4 base64 chars per 3 bytes; the regex already guarantees base64 alphabet
    approx_bytes = (len(value) - len(value.split(",", 1)[0]) - 1) * 3 // 4
    if approx_bytes > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"{field} is too large (max 2 MB)")
    return value


class SignupRequest(BaseModel):
    """Compatibility schema for the retired public student-signup service."""

    model_config = ConfigDict(hide_input_in_errors=True)

    email: EmailStr
    password: NewPassword
    role: str = "student"
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    grade: int | None = Field(default=None, ge=9, le=12)
    school: str | None = None

    @field_validator("role")
    @classmethod
    def _student_only(cls, v: str) -> str:
        if v != "student":
            raise ValueError(
                "Public student signup is disabled. "
                "Use POST /api/v1/auth/parent/register to create a parent."
            )
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    email: EmailStr
    password: ExistingPassword
    # Optional guard so a parent signing in on the student login form gets a
    # clear error instead of landing in an empty parent account. Optional, so
    # existing clients that send only email/password keep working unchanged.
    expected_role: str | None = Field(default=None, pattern="^(student|parent)$")


class ParentRegisterRequest(BaseModel):
    """Parent self-registration. Role is fixed server-side to 'parent'.

    ``extra="forbid"`` so a client that tries to smuggle in a ``role`` (or any
    other unexpected field) is rejected outright rather than silently ignored.
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: EmailStr
    password: NewPassword
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: RoleBase


class ParentRegisterResponse(TokenResponse):
    """Authenticated parent identity; child setup is a separate operation."""


class PasswordChangeResponse(TokenResponse):
    status: Literal["ok"] = "ok"
    detail: str = "Password updated"


class MeResponse(BaseModel):
    """Identity of the caller, resolved from the database (never from the JWT)."""

    id: int
    email: str
    name: str
    first_name: str = ""
    last_name: str = ""
    role: str
    grade: int | None = None
    school: str | None = None
    avatar: str | None = None
    profile_photo: str | None = None
    banner_photo: str | None = None
    onboarding_completed: bool = False
    must_change_password: bool = False
    has_local_password: bool | None = None
    needs_child_setup: bool = False


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    grade: int | None = Field(default=None, ge=9, le=12)
    school: str | None = None
    avatar: str | None = None
    headline: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    about_me: str | None = Field(default=None, max_length=2600)
    links: list[dict] | None = None
    profile_photo: str | None = None
    banner_photo: str | None = None


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    current_password: ExistingPassword
    new_password: NewPassword
