import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LinkStatus, UserRole

# Sharing scopes a student can grant a parent. Order matters: it is the order
# scopes are reported back in, and the allowlist enforced on PATCH.
LINK_SCOPES = ("basic", "insights", "memory")

# Nothing beyond basic identity/progress unless the student opts in further.
DEFAULT_LINK_SCOPES: dict[str, bool] = {"basic": True}

# How long a parent invitation stays resolvable. Prompt requirement: 14 days.
INVITE_TTL_DAYS = 14


def hash_invite_token(raw_token: str) -> str:
    """SHA-256 of an invite token, hex encoded.

    Only ever this hash is persisted. The raw token exists solely long enough to
    hand to the InviteSender, so a DB leak cannot be replayed into an approval.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


def sa_enum(enum_cls, length: int = 30):
    return Enum(enum_cls, native_enum=False, values_callable=lambda e: [m.value for m in e], length=length)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(sa_enum(UserRole), nullable=False, default=UserRole.STUDENT, server_default="student")
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    school: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="1")
    letta_agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onboarding_step: Mapped[str] = mapped_column(String(50), nullable=False, default="name", server_default="name")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    career_dna = relationship("CareerDNA", back_populates="user", uselist=False, cascade="all, delete-orphan")
    onboarding = relationship(
        "OnboardingSession", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    career_matches = relationship("CareerMatch", back_populates="user", cascade="all, delete-orphan")
    university_matches = relationship("UniversityMatch", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    roadmap_items = relationship("RoadmapItem", back_populates="user", cascade="all, delete-orphan")
    priorities = relationship("WeeklyPriority", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    passport_items = relationship("PassportItem", back_populates="user", cascade="all, delete-orphan")
    checkins = relationship("WeeklyCheckin", back_populates="user", cascade="all, delete-orphan")

    linked_children = relationship(
        "ParentStudentLink",
        foreign_keys="ParentStudentLink.parent_id",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    linked_parents = relationship(
        "ParentStudentLink",
        foreign_keys="ParentStudentLink.student_id",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def onboarding_completed(self) -> bool:
        return self.onboarding_step == "completed" or self.onboarding_completed_at is not None


class ParentStudentLink(Base):
    """A parent's request to follow a student, gated on the student's consent.

    Two shapes share this table:

    * **Claimed** -- ``student_id`` is set (immediately when the parent named an
      existing student account, or later when an invitation-only link is
      resolved on the student's first verified signup/login).
    * **Invitation-only** -- ``student_id`` is NULL and ``invited_email`` holds
      the normalized address the parent typed. ``invite_token_hash`` stores only
      a SHA-256 hash of the emailed token; ``expires_at`` bounds the invite.

    ``scopes`` is the student's sharing consent (see LINK_SCOPES) and defaults
    to just ``basic`` -- a parent never sees more by default.
    """

    __tablename__ = "parent_student_links"
    __table_args__ = (
        UniqueConstraint("parent_id", "student_id", name="uq_parent_student_links_parent_student"),
        UniqueConstraint("parent_id", "invited_email", name="uq_parent_student_links_parent_invited"),
        Index("ix_parent_student_links_student_status", "student_id", "status"),
        Index("ix_parent_student_links_invited_email", "invited_email"),
        CheckConstraint(
            "student_id IS NOT NULL OR invited_email IS NOT NULL",
            name="ck_parent_student_links_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[LinkStatus] = mapped_column(
        sa_enum(LinkStatus), default=LinkStatus.PENDING, server_default=LinkStatus.PENDING.value
    )
    label: Mapped[str] = mapped_column(String(100), default="Child", server_default="Child")
    # `basic` is not optional, so a row built without explicit scopes (a direct
    # insert, an older writer) must still grant it. `granted_scopes()` treats a
    # missing key as NOT granted, so defaulting to {} would lock a parent out.
    scopes: Mapped[dict] = mapped_column(
        JSON, default=lambda: dict(DEFAULT_LINK_SCOPES)
    )
    invited_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("User", foreign_keys=[parent_id], back_populates="linked_children")
    student = relationship("User", foreign_keys=[student_id], back_populates="linked_parents")

    # ------------------------------------------------------------------ helpers
    @property
    def scope_names(self) -> list[str]:
        """Granted scope names, restricted to the known allowlist."""
        granted = self.scopes if isinstance(self.scopes, dict) else {}
        return [name for name in LINK_SCOPES if granted.get(name) is True]

    def has_scope(self, name: str) -> bool:
        return name in self.scope_names

    @property
    def is_expired(self, now: datetime | None = None) -> bool:
        """True when a pending invitation-only link has passed its expiry.

        Never expires a claimed link: those are governed by status, not a timer.
        """
        if self.student_id is not None or not self.expires_at:
            return False
        expires = self.expires_at
        if now is None:
            now = datetime.now(timezone.utc) if expires.tzinfo else datetime.now()
        return expires < now