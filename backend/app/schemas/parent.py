"""Response schemas for parent-facing endpoints.

Every model here is an ALLOWLIST built from scratch. They do not inherit from
the internal ORM models on purpose: a new column added to e.g. ``users`` or
``career_dna`` must never appear in a parent response by accident.

Fields a parent must never receive are simply absent: conversations, DNA
``sources``/``excluded`` (raw chat quotes), check-in mood/energy/free-text
notes, weekly priorities and tasks (day-to-day activity), credentials, agent
ids, passport achievement titles, and internal numeric ids of the student's
unrelated rows.

The "Long-term memory" consent section was removed as a concept: it exposed raw
Letta archival passages and the core-memory ``human`` block. It now projects
``growth_milestones`` + ``growth_snapshots`` as "Growth history" (see
``GrowthHistory``). The internal scope key stays ``memory`` so already-stored
consents keep working with no migration of student choices.
"""

from datetime import date, datetime
from typing import Literal

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
    """A goal the student set for themselves. Title + category only."""

    id: int
    title: str
    category: str | None = None


class PassportCounts(BaseModel):
    """Passport as COUNTS ONLY.

    Deliberately no titles: an achievement title is frequently the student's own
    free-text ("Won the science fair for my anxiety project"), which would leak
    the kind of day-to-day detail parents are not entitled to. Counts carry the
    same signal without the prose.
    """

    # category -> count, only categories with count > 0.
    by_category: dict[str, int] = Field(default_factory=dict)
    total: int = 0
    verified: int = 0


class JourneyProgress(BaseModel):
    """Where the student is in the 4-year arc, in friendly language."""

    grade: int | None = None
    stage_label: str | None = None
    # 0-100 when a roadmap exists; None when there is nothing to measure.
    roadmap_percent: int | None = None


class DnaSnapshotThemes(BaseModel):
    """Top themes across the DNA. LABELS ONLY -- never ``sources``/``excluded``.

    The DNA's ``sources`` column holds verbatim chat quotes plus conversation
    ids, so it is not read for this projection at all.
    """

    themes: list[str] = Field(default_factory=list)


class BasicOverview(BaseModel):
    """The ``basic`` consent section: structure only, no free text beyond goals."""

    school: str | None = None
    career_direction: str | None = None
    profile_strength: int | None = None
    university_readiness: int | None = None
    dna_snapshot: DnaSnapshotThemes | None = None
    goals: list[OverviewGoal] = Field(default_factory=list)
    journey: JourneyProgress | None = None
    passport: PassportCounts | None = None
    # False when onboarding has not finished -- the UI shows an empty state
    # rather than a misleading "0 goals".
    onboarding_complete: bool = False


class OverviewResponse(BaseModel):
    """``basic`` scope: who they are and what they're working toward.

    Deliberately excludes anything free-text or emotional -- no check-in moods,
    no notes, no chat content, no DNA evidence, and no weekly priority/task
    text (day-to-day activity is the student's alone).
    """

    student: ParentStudentRef
    scopes: list[str] = Field(default_factory=list)
    basic: BasicOverview | None = None


# --------------------------------------------------------------------------- insights
class ParentPassportItem(BaseModel):
    """One passport entry, exposed to a parent under the ``insights`` scope.

    Full parity with the student's own passport view: ``title``,
    ``description``, ``skills``, ``date_achieved``, ``certificate_url`` and
    ``verified``. Unlike :class:`PassportCounts` this is free text the student
    wrote themselves, which is exactly why it sits behind the **revocable**
    ``insights`` consent rather than the irrevocable ``basic`` one. Revoking
    ``insights`` removes it immediately.
    """

    id: int
    category: str
    title: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    date_achieved: date | None = None
    certificate_url: str | None = None
    verified: bool = False


class InsightsResponse(BaseModel):
    """``insights`` scope: derived, high-level direction.

    Built only from the DNA's own summary fields and ranked matches. The DNA's
    ``sources`` (raw chat quotes + conversation ids) and ``excluded`` are never
    read here.
    """

    student: ParentStudentRef
    scopes: list[str] = Field(default_factory=list)
    status: str | None = None
    focus_areas: list[str] = Field(default_factory=list)
    novi_insight: str | None = None
    top_interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    career_zones: list[str] = Field(default_factory=list)
    top_career_matches: list[str] = Field(default_factory=list)
    profile_strength: int | None = None
    university_readiness: int | None = None
    passport_items: list[ParentPassportItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- growth
# Replaces the old "Long-term memory" section.
#
# The internal scope key stays ``memory`` so every stored consent keeps working
# untouched, but the section no longer exposes Letta in any form: no archival
# passages, no core-memory blocks, no ``novistate``. It is a projection of two
# of the student's OWN tables (growth_milestones, growth_snapshots).


class GrowthMilestoneOut(BaseModel):
    """A milestone the student COMPLETED. Titles only -- student-authored plans."""

    title: str
    completed_at: datetime | None = None


class GrowthTrendPoint(BaseModel):
    day: date
    # Mean confidence across the graph that day, 0-100.
    value: int


class GrowthHistory(BaseModel):
    """Parent-safe replacement for the "Long-term memory" section."""

    completed_milestones: list[GrowthMilestoneOut] = Field(default_factory=list)
    strength_trend: list[GrowthTrendPoint] = Field(default_factory=list)
    # Convenience rollups; None when there is nothing to report.
    milestones_completed: int | None = None
    trend_change: int | None = None


class MemoryResponse(BaseModel):
    """``memory`` scope -- kept as the endpoint name for stored-consent compat.

    Now a Growth-history projection. This model intentionally has NO field that
    could carry raw memory: no passage text, no summary line, no agent id.
    """

    student: ParentStudentRef
    scopes: list[str] = Field(default_factory=list)
    growth: GrowthHistory | None = None


ParentLinkOut.model_rebuild()


# --------------------------------------------------------------------------- legacy
# Retained because the existing parent frontend still calls /parents/link and
# /parents/advisor. Both now sit behind the consent flow (see services/parents.py).
class LinkStudentRequest(BaseModel):
    student_email: str = Field(min_length=3, max_length=255)


# Hard ceiling on a single parent question. A parent question is untrusted input
# that lands in an LLM prompt, so it is bounded both by length and (in the
# service) by a per-parent rate limit.
MAX_ADVISOR_QUESTION = 800

# Ceilings on the optional conversation context. These are NOT a transcript
# store: the turns travel with the request, are used for that one answer, and are
# then dropped. Nothing is written to the database, so nothing reaches the
# student's record.
MAX_ADVISOR_HISTORY_TURNS = 12
MAX_ADVISOR_HISTORY_LEN = 800


class AdvisorTurn(BaseModel):
    """One prior turn of the parent <-> Novi conversation.

    Both fields are bounded because this is parent-authored untrusted text that
    is spliced into a prompt; only ``parent`` and ``novi`` are accepted roles so
    a caller cannot forge a system turn.
    """

    role: Literal["parent", "novi"]
    content: str = Field(min_length=1, max_length=MAX_ADVISOR_HISTORY_LEN)


class AdvisorAsk(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_ADVISOR_QUESTION)
    child_id: int | None = None
    # Recent turns for conversational continuity. Bounded, ephemeral, optional --
    # omitting it keeps the original stateless one-shot behaviour.
    history: list[AdvisorTurn] = Field(
        default_factory=list, max_length=MAX_ADVISOR_HISTORY_TURNS
    )


class AdvisorResponse(BaseModel):
    answer: str