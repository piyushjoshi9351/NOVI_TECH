"""Response schemas for parent-facing endpoints.

Every model here is an ALLOWLIST built from scratch. They do not inherit from
the internal ORM models on purpose: a new column added to e.g. ``users`` or
``career_dna`` must never appear in a parent response by accident.

Fields a parent must never receive are simply absent: conversations, DNA
``sources``/``excluded`` (raw chat quotes), check-in mood/energy/free-text
notes, credentials, agent ids, and internal numeric ids of the student's
unrelated rows.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# --------------------------------------------------------------------------- links
class ParentLinkOut(ORMModel):
    """A link from the PARENT's point of view.

    Deliberately thin. For a pending link the student is usually unknown, so
    ``student`` is null and only the invited email's first name/grade are shown
    when we happen to know them.
    """

    id: int
    status: str
    label: str = ""
    scopes: list[str] = Field(default_factory=list)
    student: "ParentStudentRef | None" = None
    # The student's user id, but ONLY once the link is active -- the scoped
    # endpoints under /parent/students/{student_id}/... are keyed by it, so the
    # parent has no other way to navigate to a child they may already see.
    # Populated under exactly the same condition as `student` above, so it can
    # never reveal a student who has not consented.
    student_id: int | None = None
    invited_email_first_name: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None


class ParentLinkList(BaseModel):
    """GET /parent/students — every link this parent holds, in any state."""

    links: list[ParentLinkOut] = Field(default_factory=list)


class ParentStudentRef(ORMModel):
    """Identity only. No grade-level detail beyond what a parent needs to orient."""

    first_name: str = ""
    grade: int | None = None


class StudentLinkRequest(BaseModel):
    student_email: str = Field(min_length=3, max_length=255)
    label: str | None = Field(default=None, max_length=100)


class ParentLinkCreated(BaseModel):
    """Acknowledgement for POST /parent/links."""

    link_id: int
    status: str
    # Identical for every outcome so this endpoint cannot be used to discover
    # whether an email is registered.
    message: str


# --------------------------------------------------------------------------- student side
class StudentLinkOut(ORMModel):
    """A link from the STUDENT's point of view -- who is asking to follow me."""

    id: int
    status: str
    label: str = ""
    scopes: list[str] = Field(default_factory=list)
    parent_name: str = ""
    created_at: datetime | None = None
    expires_at: datetime | None = None


class ScopeUpdate(BaseModel):
    """Scopes the student is willing to share.

    ``basic`` is always implied and cannot be turned off, so it is not part of
    the mutable set; unknown keys are rejected rather than silently dropped.
    """

    insights: bool = False
    memory: bool = False


class StudentLinkList(BaseModel):
    links: list[StudentLinkOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- overview
class OverviewGoal(BaseModel):
    id: int
    title: str
    category: str | None = None
    status: str | None = None
    target_date: date | None = None


class OverviewPassport(BaseModel):
    id: int
    title: str
    category: str | None = None
    date_achieved: date | None = None


class OverviewRoadmapItem(BaseModel):
    id: int
    title: str
    grade: int | None = None
    stage: str | None = None
    category: str | None = None
    completed: bool = False


class OverviewWeekly(BaseModel):
    week_start: date | None = None
    priorities: list[str] = Field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0


class OverviewResponse(BaseModel):
    """``basic`` scope: who they are and what they're working toward.

    Deliberately excludes anything free-text or emotional -- no check-in moods,
    no notes, no chat content, no DNA evidence.
    """

    student: ParentStudentRef
    scopes: list[str] = Field(default_factory=list)
    school: str | None = None
    active_goals: list[OverviewGoal] = Field(default_factory=list)
    recent_passport: list[OverviewPassport] = Field(default_factory=list)
    upcoming_roadmap: list[OverviewRoadmapItem] = Field(default_factory=list)
    this_week: OverviewWeekly | None = None


# --------------------------------------------------------------------------- insights
class InsightsResponse(BaseModel):
    """``insights`` scope: derived, high-level direction.

    Built only from the DNA's own structured fields and career matches. The
    DNA's ``sources`` (raw chat quotes + conversation ids) and ``excluded`` are
    never read here.
    """

    student: ParentStudentRef
    scopes: list[str] = Field(default_factory=list)
    top_interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    career_zones: list[str] = Field(default_factory=list)
    top_career_matches: list[str] = Field(default_factory=list)
    profile_strength: int | None = None
    university_readiness: int | None = None


# --------------------------------------------------------------------------- memory
class MemoryPassage(BaseModel):
    id: str | None = None
    text: str
    created_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryResponse(BaseModel):
    """``memory`` scope: read-only, curated view of the student's Letta memory."""

    student: ParentStudentRef
    scopes: list[str] = Field(default_factory=list)
    summary: str = ""
    passages: list[MemoryPassage] = Field(default_factory=list)
    # Lets the UI distinguish "nothing shared yet" from "memory is unavailable".
    available: bool = True


ParentLinkOut.model_rebuild()


# --------------------------------------------------------------------------- legacy
# Retained because the existing parent frontend still calls /parents/link and
# /parents/advisor. Both now sit behind the consent flow (see services/parents.py).
class LinkStudentRequest(BaseModel):
    student_email: str = Field(min_length=3, max_length=255)


class AdvisorAsk(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    child_id: int | None = None


class AdvisorResponse(BaseModel):
    answer: str