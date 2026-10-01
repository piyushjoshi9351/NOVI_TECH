from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.types import TypeDecorator


class ImageData(TypeDecorator):
    """MEDIUMTEXT on MySQL (TEXT caps at 64 KB, far too small for a photo).

    Renders as TEXT elsewhere so the SQLite-backed test suite still works —
    SQLite has no length limit that matters here.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(MEDIUMTEXT())
        return dialect.type_descriptor(Text())
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UserRole


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
    # LinkedIn-style profile media + About copy. Stored as data URLs so the
    # app needs no object storage or upload service.
    profile_photo: Mapped[str | None] = mapped_column(ImageData, nullable=True)
    banner_photo: Mapped[str | None] = mapped_column(ImageData, nullable=True)
    about_me: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    links: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="1")
    letta_agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onboarding_step: Mapped[str] = mapped_column(String(50), nullable=False, default="name", server_default="name")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dna_snapshots = relationship("CareerDNASnapshot", back_populates="user", cascade="all, delete-orphan")
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
    __tablename__ = "parent_student_links"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("User", foreign_keys=[parent_id], back_populates="linked_children")
    student = relationship("User", foreign_keys=[student_id], back_populates="linked_parents")