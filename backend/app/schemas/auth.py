import re

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import ORMModel, RoleBase, USER_ROLES

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
    """Student self-registration. The role is fixed server-side to 'student'.

    ``role`` is kept as an accepted field purely for backwards compatibility --
    both existing frontend signup forms send it -- but the only legal value is
    ``'student'``. Parent accounts can only be created through
    ``POST /auth/parent/register`` (or the Google flow with a signed intent), so
    that invitation/consent state is always set up correctly and a client can
    never mint a parent by posting to the generic signup route.
    """

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
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
                "This endpoint only creates student accounts. "
                "Use POST /api/v1/auth/parent/register to create a parent."
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Optional guard so a parent signing in on the student login form gets a
    # clear error instead of landing in an empty parent account. Optional, so
    # existing clients that send only email/password keep working unchanged.
    expected_role: str | None = Field(default=None, pattern="^(student|parent)$")


class ParentRegisterRequest(BaseModel):
    """Parent self-registration. Role is fixed server-side to 'parent'.

    ``extra="forbid"`` so a client that tries to smuggle in a ``role`` (or any
    other unexpected field) is rejected outright rather than silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    student_email: EmailStr


class ParentRegisterResponse(BaseModel):
    user: RoleBase
    # The invitation we created, so the UI can show "request sent" immediately.
    link_id: int
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: RoleBase


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
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)