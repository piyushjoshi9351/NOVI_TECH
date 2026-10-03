from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class UniversityOut(ORMModel):
    id: int
    slug: str
    name: str
    country: str
    city: str
    course: str
    subject: str
    ranking: int | None = None
    fees_per_year: int | None = None
    university_type: str
    scholarships: bool = False
    entry_requirements: str
    about: str
    website: str | None = None
    tags: list | None = None
    strengths: list | None = None
    courses: list | None = None
    rankings: dict | None = None


class UniversityMatchOut(ORMModel):
    id: int
    readiness: float
    strengths: list | None = None
    improvements: list | None = None
    next_steps: list | None = None
    university: UniversityOut | None = None
    reason: str | None = None


class ReadinessRequest(BaseModel):
    university_id: int
    course: str | None = None


class AdviceSource(BaseModel):
    title: str = ""
    uri: str = ""
    domain: str = ""


class AdviceOut(BaseModel):
    answer: str
    sources: list[AdviceSource] = []
    candidates: list[UniversityOut] = []


class AdviceRequest(BaseModel):
    question: str = "Which university is best for me?"
    subject: str | None = None
    university_ids: list[int] | None = None


class UniversityFilters(BaseModel):
    q: str | None = None
    course: str | None = None
    entry_query: str | None = None
    country: str | None = None
    subject: str | None = None
    min_rank: int | None = Field(default=None, ge=1)
    max_fees: int | None = Field(default=None, ge=0)
    university_type: str | None = None
    scholarships: bool | None = None
    limit: int = Field(default=30, ge=1, le=100)
