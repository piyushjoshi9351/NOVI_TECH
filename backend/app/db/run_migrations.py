"""Minimal, dependency-free SQL migration runner.

Scans backend/migrations/*.sql (numbered 0001_, 0002_, ...) in filename order
and applies any file not yet recorded in schema_migrations. Each file runs in
its own transaction and is recorded only after every statement succeeds, so a
partial or failed migration never gets silently skipped on a later startup.

There is no Alembic: this is intentionally a thin layer over what the repo
already does with create_all() + .sql files.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.core.config import BACKEND_DIR
from app.core.database import engine

# Make the runner's INFO logs visible even when it is invoked outside the app
# (e.g. python -m app.db.init_db), which does not call main.py's basicConfig.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

logger = logging.getLogger("novi.migrations")

MIGRATIONS_DIR = BACKEND_DIR / "migrations"

# Belt-and-suspenders list for the startup sanity check. If any of these
# columns is missing the app logs a CRITICAL warning (it never crashes).
CRITICAL_COLUMNS = [
    ("users", "onboarding_step"),
    ("users", "onboarding_completed_at"),
]


def _statements(path: Path) -> list[str]:
    """Split a migration file into individual statements.

    Statements are terminated by ';' and full-line ``--`` comments are dropped.

    Comments are stripped BEFORE the split, not after. Splitting first looks
    equivalent but isn't: a multi-line comment that mentions ';' (very easy when
    documenting this runner, ironically) would be cut in half, and the surviving
    fragment would be glued onto the front of the next statement, producing
    invalid SQL that fails at apply time.

    Assumes no ';' or '--' inside string literals, which holds for the migrations
    in this repo and keeps the runner free of a real SQL parser.
    """
    raw = path.read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    body = "\n".join(lines)
    statements = []
    for chunk in body.split(";"):
        stmt = " ".join(chunk.split()).strip()
        if stmt:
            statements.append(stmt)
    return statements


def run_migrations() -> None:
    """Apply pending backend/migrations/*.sql files in order.

    Raises on the first failing migration: nothing further is applied and the
    file is not recorded in schema_migrations. Callers (app startup, init_db)
    let the exception propagate so the app fails to start rather than coming up
    in a half-migrated state.
    """
    if not MIGRATIONS_DIR.is_dir():
        logger.info("no migrations directory at %s", MIGRATIONS_DIR)
        return

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        name = path.name
        with engine.begin() as conn:
            already_applied = conn.execute(
                text("SELECT 1 FROM schema_migrations WHERE filename = :name"),
                {"name": name},
            ).first()
            if already_applied:
                logger.info("migration %s already applied, skipping", name)
                continue

            # Statements run on the same connection/session: migration files may
            # use MySQL PREPARE/EXECUTE (session-scoped) and MySQL DDL
            # auto-commits anyway, so the transaction cannot fully roll DDL back
            # — but a failure still stops the run and skips recording the file.
            for stmt in _statements(path):
                conn.execute(text(stmt))

            conn.execute(
                text(
                    "INSERT INTO schema_migrations (filename, applied_at) VALUES (:name, :applied_at)"
                ),
                {"name": name, "applied_at": datetime.now(timezone.utc)},
            )
        logger.info("migration %s applied", name)


def check_critical_columns() -> None:
    """Log CRITICAL warnings for any required column that is missing.

    Independent safety net that catches migrations being bypassed entirely
    (e.g. a manual DB restore or a misconfigured deploy). Never raises — the
    intent is an unmissable log line, not a crash.
    """
    schema = engine.url.database
    missing = []
    with engine.connect() as conn:
        for table, column in CRITICAL_COLUMNS:
            found = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
                ),
                {"schema": schema, "table": table, "column": column},
            ).first()
            if not found:
                missing.append(f"{table}.{column}")
    for name in missing:
        logger.critical("CRITICAL: required column %s is MISSING in database %s", name, schema)