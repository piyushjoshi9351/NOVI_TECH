"""End-to-end verification of 0004_parent_student_links_invites.sql against MySQL.

Runs the real migration runner against a throwaway database that is seeded with
the PRE-migration table shape and rows, then asserts:

  * the backfill grandfathered existing links as active + basic,
  * student_id is nullable and the CHECK constraint holds,
  * all unique keys/indexes exist,
  * re-running the migration is a no-op (idempotency).

Usage:  python -m scripts.verify_migration_0004
Not part of the pytest suite (needs a live MySQL); run it deliberately.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import run_migrations as runner  # noqa: E402

SCRATCH_DB = "novi_mig0004_test"

OLD_SCHEMA = """
CREATE TABLE `parent_student_links` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,
  `parent_id` INTEGER NOT NULL,
  `student_id` INTEGER NOT NULL,
  `label` VARCHAR(50) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_parent_student_links_parent_id` (`parent_id`),
  KEY `ix_parent_student_links_student_id` (`student_id`),
  CONSTRAINT `fk_psl_parent` FOREIGN KEY (`parent_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_psl_student` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB
"""

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -> ' + detail) if detail and not ok else ''}")
    if not ok:
        FAILS.append(label)


def main() -> int:
    url = make_url(settings.database_url)
    root_url = url.set(database="mysql")
    scratch_url = url.set(database=SCRATCH_DB)

    root = create_engine(root_url)
    scratch = create_engine(scratch_url)

    with root.begin() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
        c.execute(text(f"CREATE DATABASE `{SCRATCH_DB}`"))

    try:
        with scratch.begin() as c:
            # Minimal users table so the FKs are valid.
            c.execute(text("""
                CREATE TABLE `users` (
                  `id` INTEGER NOT NULL AUTO_INCREMENT,
                  `email` VARCHAR(255) NOT NULL,
                  PRIMARY KEY (`id`)
                ) ENGINE=InnoDB
            """))
            # The runner reads this ledger before anything else.
            c.execute(text("""
                CREATE TABLE `schema_migrations` (
                  `filename` VARCHAR(255) NOT NULL,
                  `applied_at` DATETIME NOT NULL,
                  PRIMARY KEY (`filename`)
                ) ENGINE=InnoDB
            """))
            c.execute(text(OLD_SCHEMA))
            # Pretend the earlier migrations already ran: this script only cares
            # about 0004, and 0001/0002 need the full app schema.
            c.execute(text(
                "INSERT INTO schema_migrations (filename, applied_at) VALUES "
                "('0001_conversational_onboarding.sql', NOW()), ('0002_m3_goals_legacy_goal_id.sql', NOW())"
            ))
            c.execute(text("INSERT INTO users (id, email) VALUES (1,'p@e.com'), (2,'s@e.com'), (3,'s2@e.com')"))
            # Two pre-existing links, plus a duplicate pair to prove de-dup works.
            c.execute(text("""
                INSERT INTO parent_student_links (parent_id, student_id, label, created_at) VALUES
                  (1, 2, 'Old Child', NOW()),
                  (1, 2, 'Duplicate', NOW()),
                  (1, 3, 'Other', NOW())
            """))

        print("\n1. Apply migration to the old schema")
        runner.engine = scratch
        runner.run_migrations()
        check("migration applied without error", True)

        with scratch.connect() as c:
            cols = {
                r[0]: (r[1], r[2])
                for r in c.execute(text("""
                    SELECT COLUMN_NAME, IS_NULLABLE, COLUMN_DEFAULT
                    FROM information_schema.columns
                    WHERE table_schema=DATABASE() AND table_name='parent_student_links'
                """))
            }
            check("student_id is nullable", cols["student_id"][0] == "YES", str(cols["student_id"]))
            check("status is NOT NULL", cols["status"][0] == "NO", str(cols["status"]))
            check("status defaults to 'pending'", cols["status"][1] == "pending", str(cols["status"]))
            check("scopes is NOT NULL", cols["scopes"][0] == "NO", str(cols["scopes"]))
            for col in ("invited_email", "invite_token_hash", "expires_at", "confirmed_at", "revoked_at"):
                check(f"{col} exists", col in cols)

            idx = {
                r[0]
                for r in c.execute(text("""
                    SELECT DISTINCT INDEX_NAME FROM information_schema.statistics
                    WHERE table_schema=DATABASE() AND table_name='parent_student_links'
                """))
            }
            for name in (
                "uq_parent_student_links_parent_student",
                "uq_parent_student_links_parent_invited",
                "ix_parent_student_links_student_status",
                "ix_parent_student_links_invited_email",
            ):
                check(f"index {name} exists", name in idx)

            checks = {
                r[0]
                for r in c.execute(text("""
                    SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
                    WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME='parent_student_links'
                      AND CONSTRAINT_TYPE='CHECK'
                """))
            }
            check("CHECK constraint exists", "ck_parent_student_links_target" in checks)

        print("\n2. Backfill of pre-existing links")
        with scratch.connect() as c:
            rows = list(
                c.execute(text("SELECT id, student_id, status, scopes, confirmed_at FROM parent_student_links ORDER BY id"))
            )
            check("duplicate row was de-duped", len(rows) == 2, f"{len(rows)} rows")
            check(
                "all backfilled rows are active",
                all(r[2] == "active" for r in rows),
                str([r[2] for r in rows]),
            )
            check(
                "all backfilled rows default to basic scope",
                all('"basic": true' in str(r[3]) for r in rows),
                str([r[3] for r in rows]),
            )
            check(
                "confirmed_at stamped from created_at",
                all(r[4] is not None for r in rows),
            )

        print("\n3. New invitation-only rows are allowed")
        with scratch.begin() as c:
            c.execute(text("""
                INSERT INTO parent_student_links
                  (parent_id, student_id, status, label, scopes, invited_email, invite_token_hash, expires_at)
                VALUES (1, NULL, 'pending', 'Invited', JSON_OBJECT('basic', TRUE),
                        'ghost@e.com', 'hash123', NOW() + INTERVAL 14 DAY)
            """))
        with scratch.connect() as c:
            n = c.execute(text("SELECT COUNT(*) FROM parent_student_links WHERE student_id IS NULL")).scalar()
            check("NULL student_id row persisted", n == 1)

        print("\n4. CHECK constraint rejects a target-less link")
        try:
            with scratch.begin() as c:
                c.execute(text("""
                    INSERT INTO parent_student_links (parent_id, student_id, status, label, scopes)
                    VALUES (1, NULL, 'pending', 'Bad', JSON_OBJECT('basic', TRUE))
                """))
            check("CHECK rejects student_id NULL + invited_email NULL", False, "insert succeeded")
        except Exception:
            check("CHECK rejects student_id NULL + invited_email NULL", True)

        print("\n5. Idempotency: re-run the whole migration")
        try:
            with scratch.begin() as c:
                c.execute(text("DELETE FROM schema_migrations"))
                c.execute(text(
                    "INSERT INTO schema_migrations (filename, applied_at) VALUES "
                    "('0001_conversational_onboarding.sql', NOW()), ('0002_m3_goals_legacy_goal_id.sql', NOW())"
                ))
            runner.run_migrations()
            check("second run succeeded", True)
        except Exception as exc:
            check("second run succeeded", False, str(exc)[:200])

        with scratch.connect() as c:
            n = c.execute(text("SELECT COUNT(*) FROM parent_student_links")).scalar()
            check("row count unchanged after re-run", n == 3, f"count={n}")
            col = {
                r[0]: r[1]
                for r in c.execute(text("""
                    SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.columns
                    WHERE table_schema=DATABASE() AND table_name='parent_student_links'
                """))
            }
            check("student_id still nullable after re-run", col["student_id"] == "YES")

    finally:
        with root.begin() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS `{SCRATCH_DB}`"))
        scratch.dispose()
        root.dispose()

    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())