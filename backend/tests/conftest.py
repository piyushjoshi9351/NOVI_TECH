"""Shared pytest fixtures for the NOVI backend tests.

Tests run against an isolated in-memory SQLite database. The production MySQL
engine created at import time is never used here; only the ORM metadata on the
two declarative bases (legacy ``app.core.database.Base`` and module-3
``app.m3.db.models.Base``) is reused.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Keep tests hermetic: a dummy key lets the Gemini client construct without a
# real credential (it is never called), and Letta memory stays disabled.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")
os.environ.setdefault("LETTA_ENABLED", "false")

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: E402,F401  (registers every legacy table)
from app.core.database import Base as LegacyBase  # noqa: E402
from app.m3.db import models as m3_models  # noqa: E402,F401  (registers m3 tables)
from app.m3.db.models import Base as M3Base  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LegacyBase.metadata.create_all(bind=engine)
    M3Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user(db):
    student = User(
        email="student@example.com",
        password_hash="not-a-real-hash",
        first_name="Test",
        last_name="Student",
        grade=10,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


# ----------------------------------------------------------------- parent linking
@pytest.fixture()
def parent(db):
    from app.models.user import User

    p = User(
        email="parent@example.com",
        password_hash="not-a-real-hash",
        first_name="Pat",
        last_name="Parent",
        role=UserRole.PARENT,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def other_parent(db):
    from app.models.user import User

    p = User(
        email="other-parent@example.com",
        password_hash="not-a-real-hash",
        first_name="Otto",
        last_name="Other",
        role=UserRole.PARENT,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def other_student(db):
    from app.models.user import User

    s = User(
        email="other-student@example.com",
        password_hash="not-a-real-hash",
        first_name="Other",
        last_name="Student",
        grade=11,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture()
def active_link(db, parent, user):
    """An APPROVED parent->student link (the only state that grants access)."""
    from app.models.enums import LinkStatus
    from app.models.user import DEFAULT_LINK_SCOPES, ParentStudentLink

    link = ParentStudentLink(
        parent_id=parent.id,
        student_id=user.id,
        status=LinkStatus.ACTIVE,
        label="Child",
        scopes=dict(DEFAULT_LINK_SCOPES),
        invited_email=user.email,
        confirmed_at=datetime.now(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@pytest.fixture()
def pending_link(db, parent, user):
    from app.models.enums import LinkStatus
    from app.models.user import DEFAULT_LINK_SCOPES, ParentStudentLink

    link = ParentStudentLink(
        parent_id=parent.id,
        student_id=user.id,
        status=LinkStatus.PENDING,
        label="Child",
        scopes=dict(DEFAULT_LINK_SCOPES),
        invited_email=user.email,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@pytest.fixture()
def client(db):
    """TestClient wired to the in-memory session.

    get_db is overridden to yield the SAME session the fixtures use, so objects
    created in a test are visible to the app under test.

    Deliberately NOT used as a context manager: entering `with TestClient(app)`
    runs the FastAPI lifespan, which calls Base.metadata.create_all() and
    run_migrations() against the PRODUCTION MySQL engine. Tests must never
    mutate a real database, so the lifespan is left unstarted.
    """
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_header(user_id: int, role: str = "student") -> dict:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(str(user_id), role)}"}
