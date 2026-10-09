"""Conversational onboarding storage.

- ``onboarding_answers`` — append-only log of the raw value captured per step.
- ``student_profile`` — the distilled per-student profile written from those
  answers (one row per student, keyed on ``users.id``).

Datetimes follow the app convention: timezone-aware in Python
(``datetime.now(timezone.utc)``), stored as naive UTC in MySQL DATETIME.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OnboardingAnswer(Base):
    """One row per answered step; the raw value as captured, never overwritten."""

    __tablename__ = "onboarding_answers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_id: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentProfile(Base):
    """The distilled profile produced by the conversational onboarding."""

    __tablename__ = "student_profile"

    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    curriculum_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grade_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    saturday_activities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    strengths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enjoyed_subjects: Mapped[list | None] = mapped_column(JSON, nullable=True)
    difficult_subjects: Mapped[list | None] = mapped_column(JSON, nullable=True)
    learning_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_choice: Mapped[str | None] = mapped_column(String(50), nullable=True)
    university_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    university_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    university_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    university_extraction_conf: Mapped[str | None] = mapped_column(String(50), nullable=True)
    has_career_in_mind: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    career_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    career_interest_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )