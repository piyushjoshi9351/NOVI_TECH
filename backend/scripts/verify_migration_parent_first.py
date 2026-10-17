"""Rehearse all migrations and a pre-0008 upgrade in a private MySQL container.

No application URL, database credentials, Compose files or external volumes are
used. Data lives on tmpfs in a new, labelled container; it is removed on exit.
The old-schema dump contains synthetic rows only and never leaves memory.
Run: python -X utf8 backend/scripts/verify_migration_parent_first.py
"""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
NEW_COLUMNS = {
    "users": {"must_change_password", "token_version", "created_by_parent_id", "has_local_password", "first_login_at"},
    "parent_student_links": {"activation_source", "activated_at"},
}
REPORT = ROOT / "docs/verification/parent-first-migration.json"


def require(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}", flush=True)


def old_column_names():
    source = subprocess.run(["git", "show", "HEAD:backend/app/models/user.py"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    tree = ast.parse(source)
    names = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in ("User", "ParentStudentLink"):
            names["users" if node.name == "User" else "parent_student_links"] = {
                item.target.id for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.value, ast.Call)
                and isinstance(item.value.func, ast.Name) and item.value.func.id == "mapped_column"
            }
    # After this refactor is committed, its known additive columns are excluded.
    return {table: columns - NEW_COLUMNS[table] for table, columns in names.items()}


def snapshot(engine, table, columns):
    selected = ", ".join(f"`{column}`" for column in sorted(columns))
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(text(f"SELECT {selected} FROM `{table}` ORDER BY id")).mappings()]
    for row in rows:
        for column in ("scopes", "links"):
            if isinstance(row.get(column), str):
                row[column] = json.loads(row[column])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker-cli", default=shutil.which("docker") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin/docker.exe"))
    parser.add_argument("--image", default="mysql:8.0")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    nonce = uuid.uuid4().hex
    name = f"novi-parent-first-verify-{nonce[:12]}"
    password = secrets.token_urlsafe(32)
    environment = {**os.environ, "MYSQL_ROOT_PASSWORD": password, "MYSQL_PWD": password}
    container = None
    engines = []
    report = {"status": "failed", "image": args.image, "started_at": datetime.now(timezone.utc).isoformat()}

    def docker(*command, data=None, timeout=240):
        result = subprocess.run([args.docker_cli, *command], input=data, env=environment, capture_output=True, timeout=timeout)
        if result.returncode:
            # Never echo command output: database diagnostics may include inputs.
            raise RuntimeError(f"Docker {command[0]} failed (exit {result.returncode})")
        return result.stdout

    def owned():
        info = json.loads(docker("inspect", container))[0]
        require(info["Config"]["Labels"].get("novi.parent-first-rehearsal") == nonce, "container ownership verified")
        require(all(mount["Type"] == "tmpfs" for mount in info["Mounts"]), "no bind mounts or Docker volumes attached")
        return info

    def database(db_name):
        with admin.begin() as conn:
            conn.execute(text(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        engine = create_engine(URL.create("mysql+pymysql", username="root", password=password, host="127.0.0.1", port=port, database=db_name))
        engines.append(engine)
        return engine

    def apply(engine):
        runner.engine = engine
        runner.run_migrations()

    try:
        docker("version", "--format", "{{.Server.Version}}", timeout=30)
        print("Starting isolated MySQL on tmpfs; project volumes are not used.", flush=True)
        container = docker("run", "--detach", "--rm", "--name", name,
            "--label", f"novi.parent-first-rehearsal={nonce}",
            "--mount", "type=tmpfs,destination=/var/lib/mysql,tmpfs-size=1073741824",
            "--publish", "127.0.0.1::3306", "--env", "MYSQL_ROOT_PASSWORD", "--env", "MYSQL_ROOT_HOST=%", args.image).decode().strip()
        info = owned()
        port = int(info["NetworkSettings"]["Ports"]["3306/tcp"][0]["HostPort"])
        admin = create_engine(URL.create("mysql+pymysql", username="root", password=password, host="127.0.0.1", port=port, database="mysql"), connect_args={"connect_timeout": 2})
        engines.append(admin)
        deadline = time.monotonic() + 180
        while True:
            try:
                with admin.connect() as conn:
                    report["mysql_version"] = conn.execute(text("SELECT VERSION()")).scalar_one()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Private MySQL did not become ready") from None
                time.sleep(1)

        # Ensure imports cannot construct a connection to the configured app DB.
        os.environ.update(DB_HOST="127.0.0.1", DB_PORT=str(port), DB_USER="root", DB_PASSWORD=password,
            DB_NAME="pf_fresh", ENVIRONMENT="test", LETTA_ENABLED="false")
        from app import models  # noqa: F401
        from app.core.database import Base
        from app.m3.db.models import Base as M3Base
        from app.db import run_migrations as runner
        from app.core.security import hash_password

        additive = []
        for filename in ("0008_parent_provisioned_students.sql", "0009_account_sign_in_metadata.sql"):
            path = runner.MIGRATIONS_DIR / filename
            statements = runner._statements(path)
            ddl = [match for statement in statements for match in re.findall(r"'(ALTER TABLE [^']+)'", statement)]
            require(bool(ddl) and all(re.match(r"ALTER TABLE `(?:users|parent_student_links)` ADD (?:COLUMN|INDEX|CONSTRAINT)\b", item) for item in ddl), f"{filename}: additive DDL only")
            require(all(statement.split()[0].upper() in {"SET", "PREPARE", "EXECUTE", "DEALLOCATE"} for statement in statements), f"{filename}: no data-rewrite statements")
            additive.append({"file": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "additive_operations": len(ddl)})
        report["migration_review"] = additive

        fresh = database("pf_fresh")
        Base.metadata.create_all(fresh)
        M3Base.metadata.create_all(fresh)
        apply(fresh)
        apply(fresh)
        with fresh.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar_one()
        require(count == len(list(runner.MIGRATIONS_DIR.glob("*.sql"))), "all migrations succeed on an empty app database; ledger replay is safe")
        report["fresh_migrations"] = count

        source = database("pf_pre_0008")
        Base.metadata.create_all(source)
        M3Base.metadata.create_all(source)
        # Apply 0001-0007, then export the precise pre-refactor table shape.
        with source.begin() as conn:
            for path in sorted(runner.MIGRATIONS_DIR.glob("*.sql")):
                if path.name.startswith(("0008_", "0009_")):
                    continue
                for statement in runner._statements(path):
                    conn.execute(text(statement))
                conn.execute(text("INSERT INTO schema_migrations VALUES (:name, UTC_TIMESTAMP())"), {"name": path.name})
        inspector = inspect(source)
        with source.begin() as conn:
            for fk in inspector.get_foreign_keys("users"):
                if "created_by_parent_id" in fk["constrained_columns"]:
                    conn.execute(text(f"ALTER TABLE users DROP FOREIGN KEY `{fk['name']}`"))
            conn.execute(text("ALTER TABLE users DROP INDEX ix_users_created_by_parent_id"))
            for table, columns in NEW_COLUMNS.items():
                for column in sorted(columns):
                    conn.execute(text(f"ALTER TABLE `{table}` DROP COLUMN `{column}`"))
        legacy_columns = old_column_names()
        for table, expected in legacy_columns.items():
            require({col["name"] for col in inspect(source).get_columns(table)} == expected, f"{table}: restored schema matches committed pre-refactor columns")

        with source.begin() as conn:
            for user_id, role in ((1, "parent"), (2, "parent"), (11, "student"), (12, "student"), (13, "student"), (14, "student"), (15, "student"), (16, "parent")):
                conn.execute(text("INSERT INTO users (id,email,password_hash,role,first_name,last_name,is_active,onboarding_step) VALUES (:id,:email,:hash,:role,'Fixture','User',1,'name')"),
                    {"id": user_id, "email": f"fixture-{user_id}@example.invalid", "hash": hash_password(secrets.token_urlsafe(32) if user_id in (15, 16) else "Fixture-password"), "role": role})
            fixtures = [
                (101, 1, 11, "active", {"basic": True, "insights": True, "memory": False, "legacy_extra": 7}, None),
                (102, 2, 11, "active", {"basic": True, "memory": True}, None),
                (103, 1, 12, "revoked", {"basic": False, "insights": True}, None),
                (104, 1, 13, "pending", {"basic": True, "insights": False}, None),
                (105, 1, None, "pending", {"basic": True, "memory": False}, "unclaimed@example.invalid"),
                (106, 2, None, "revoked", {"basic": True}, "removed@example.invalid"),
                (107, 2, 15, "active", {"basic": True}, None),
            ]
            for link_id, parent_id, student_id, status, scopes, email in fixtures:
                conn.execute(text("INSERT INTO parent_student_links (id,parent_id,student_id,status,label,scopes,invited_email,invite_token_hash,expires_at,confirmed_at,revoked_at) VALUES (:id,:parent,:student,:status,'Fixture',:scopes,:email,:hash,:expires,:confirmed,:revoked)"),
                    {"id": link_id, "parent": parent_id, "student": student_id, "status": status, "scopes": json.dumps(scopes), "email": email,
                     "hash": "a" * 64 if email else None, "expires": datetime(2020, 1, 1) if email else None,
                     "confirmed": datetime(2019, 1, 1) if status in ("active", "revoked") else None,
                     "revoked": datetime(2020, 2, 1) if status == "revoked" else None})
            # Legacy Google provenance was never stored: random bcrypt hashes
            # remain unknown, including both a Google student and parent.
            conn.execute(text("UPDATE users SET avatar='https://example.invalid/google-avatar' WHERE id IN (15,16)"))
        before = {table: snapshot(source, table, columns) for table, columns in legacy_columns.items()}

        dump = docker("exec", "--env", "MYSQL_PWD", container, "mysqldump", "-uroot", "--set-gtid-purged=OFF", "--column-statistics=0", "pf_pre_0008")
        restored = database("pf_restored")
        docker("exec", "--interactive", "--env", "MYSQL_PWD", container, "mysql", "-uroot", "pf_restored", data=dump)
        require(all(snapshot(restored, table, columns) == before[table] for table, columns in legacy_columns.items()), "synthetic old-schema dump restored without changes")
        apply(restored)

        def preservation():
            for table, columns in legacy_columns.items():
                require(snapshot(restored, table, columns) == before[table], f"{table}: IDs, roles, hashes, statuses, scopes and historical fields unchanged")
            with restored.connect() as conn:
                users = conn.execute(text("SELECT token_version,must_change_password,created_by_parent_id,has_local_password,first_login_at FROM users")).all()
                links = conn.execute(text("SELECT activation_source,activated_at FROM parent_student_links")).all()
                require(all(tuple(row) == (0, 0, None, None, None) for row in users), "all legacy users have safe defaults: version 0, no forced password reset, unknown provenance")
                require(all(tuple(row) == (None, None) for row in links), "no activation provenance or timestamps fabricated")
        preservation()
        # Re-run actual additive SQL, not just the ledger's no-op branch.
        with restored.begin() as conn:
            conn.execute(text("DELETE FROM schema_migrations WHERE filename IN ('0008_parent_provisioned_students.sql','0009_account_sign_in_metadata.sql')"))
        apply(restored)
        preservation()
        require(any(row["id"] == 14 for row in before["users"]), "student without a parent survives")
        require(all(row["status"] == "revoked" for row in snapshot(restored, "parent_student_links", {"id", "status"}) if row["id"] in (103, 106)), "revoked links never reactivate")
        require(all(row["status"] == "pending" for row in snapshot(restored, "parent_student_links", {"id", "status"}) if row["id"] in (104, 105)), "pending and invitation-only links never auto-activate")
        report.update(status="passed", legacy_users=len(before["users"]), legacy_links=len(before["parent_student_links"]),
            scenarios=["active links with exact scopes", "multiple parents", "revoked links", "pending linked students", "expired invitation-only links", "revoked invitation", "student without parent", "legacy Google student and parent"],
            preservation="all legacy columns equal before and after upgrade and explicit replay", storage="tmpfs only; no project or external volumes", synthetic_restore=True)
    except Exception as exc:
        report["failure"] = type(exc).__name__
        print(f"FAIL: rehearsal stopped ({type(exc).__name__}); no credential values displayed", flush=True)
        # Assertions and our own operational messages contain labels only.
        if isinstance(exc, (AssertionError, RuntimeError)):
            print(str(exc), flush=True)
    finally:
        for engine in reversed(engines):
            engine.dispose()
        if container:
            owned()
            docker("stop", "--time", "10", container, timeout=45)
            report["container_removed"] = True
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
