from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.common import ORMModel, RoleBase, USER_ROLES


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
    onboarding_completed: bool = False


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    grade: int | None = Field(default=None, ge=9, le=12)
    school: str | None = None
    avatar: str | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)