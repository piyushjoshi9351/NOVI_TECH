import re

from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, Field

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
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="student", pattern="^(student|parent)$")
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    grade: int | None = Field(default=None, ge=9, le=12)
    school: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: RoleBase


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