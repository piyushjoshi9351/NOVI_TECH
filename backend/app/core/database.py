from datetime import datetime

from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


class SchemaMigration(Base):
    """Tracks which backend/migrations/*.sql files have been applied."""

    __tablename__ = "schema_migrations"
    __table_args__ = {"mysql_engine": "InnoDB"}

    filename: Mapped[str] = mapped_column(String(255), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()