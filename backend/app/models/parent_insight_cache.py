"""Cache for the parent-facing "Novi's insight" card.

One row per (student, snapshot-hash). The hash is taken over the
**consented parent-safe snapshot only** -- see
``app.services.parent_projection.consented_snapshot`` -- so revoking a consent
section changes the key and the previously generated insight is never served
again. That is what makes revocation immediate rather than eventual.

Why a table rather than Redis: nothing else in the codebase uses Redis, so a
table is one fewer moving part and is trivially testable. The read path is a
single indexed SELECT and the row is tiny.

This is a CACHE, not a record of consent or of access: nothing here is
authoritative, and deleting every row only costs one extra LLM call.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ParentInsightCache(Base):
    __tablename__ = "parent_insight_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # SHA-256 of the consented parent-safe snapshot. Changing consent changes
    # this value, which is the whole invalidation mechanism.
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    insight: Mapped[str] = mapped_column(Text, default="")
    # "llm" or "template" -- lets tests and ops see which path produced a card.
    source: Mapped[str] = mapped_column(String(16), default="template")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "snapshot_hash", name="uq_parent_insight_snapshot"),
        Index("ix_parent_insight_expires", "expires_at"),
    )