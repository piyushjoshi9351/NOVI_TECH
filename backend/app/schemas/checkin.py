from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CheckinCreate(BaseModel):
    week_start: date | None = None
    accomplishments: str = ""
    learnings: str = ""
    challenges: str = ""
    pride: str = ""
    next_week: str = ""


class CheckinOut(ORMModel):
    id: int
    week_start: date
    accomplishments: str
    learnings: str
    challenges: str
    pride: str
    next_week: str
    ai_summary: dict | None = None
    status: str
    updated_at: datetime | None = None


class CheckinSummaryOut(BaseModel):
    wins: int = 0
    new_skills: list[str] = []
    milestones: list[str] = []
    priorities_next_week: list[str] = []


class ContributionCell(BaseModel):
    date: date
    level: int          # 0-4, GitHub-style intensity
    count: int          # activity points behind the level
    kind: str = ""      # "daily" | "weekly" | "both" | ""
    note: str = ""      # tooltip text


class ContributionWeek(BaseModel):
    week_start: date
    days: list[ContributionCell]
    weekly_done: bool = False   # weekly reflection submitted for this week


class ContributionStats(BaseModel):
    current_streak: int = 0
    best_streak: int = 0
    active_days: int = 0
    weekly_done: int = 0


class ContributionGraphOut(BaseModel):
    weeks: list[ContributionWeek]
    stats: ContributionStats