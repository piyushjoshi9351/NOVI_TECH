from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

USER_ROLES = ("student", "parent")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RoleBase(ORMModel):
    id: int
    email: str
    role: str
    first_name: str = ""
    last_name: str = ""
    grade: int | None = None
    school: str | None = None
    avatar: str | None = None
    profile_photo: str | None = None
    banner_photo: str | None = None
    about_me: str | None = None
    headline: str | None = None
    location: str | None = None
    links: list | None = None
    letta_agent_id: str | None = None
    created_at: datetime | None = None
    onboarding_step: str | None = None
    onboarding_completed_at: datetime | None = None
    onboarding_completed: bool = False


def dt_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def months_since(d: datetime | None) -> int:
    if not d:
        return 0
    now = datetime.now(d.tzinfo) if d.tzinfo else datetime.now()
    return max(0, (now.year - d.year) * 12 + (now.month - d.month))