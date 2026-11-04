"""Read-only diagnostic for the NOVI MySQL connection.

Run from the repository root:
    python test_db_connection.py

This script loads backend/.env, never prints secret values, and only executes
SELECT VERSION(), DATABASE().
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except ImportError as exc:
    print("FAILURE: python-dotenv is required to load backend/.env.")
    print(f"{type(exc).__name__}: {exc}")
    sys.exit(2)


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / "backend" / ".env"
REQUIRED_VARS = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")
TIMEOUTS = {"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30}


def _safe_error(exc: BaseException, secret: str) -> str:
    """Return an exception message with credentials and URL-like values removed."""
    message = str(exc).replace(secret, "<redacted>")
    message = re.sub(r"(mysql\+pymysql://)[^@\s]+@", r"\1<redacted>@", message)
    message = re.sub(r"(?i)(password|passwd|pwd)\s*=\s*[^\s,;]+", r"\1=<redacted>", message)
    return message or "<no error message>"


def _configuration() -> tuple[dict[str, str], str | None]:
    if not ENV_FILE.is_file():
        return {}, f"Required environment file not found: {ENV_FILE}"

    load_dotenv(ENV_FILE, override=False)
    values = {name: os.getenv(name, "").strip() for name in REQUIRED_VARS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        return values, "Missing required environment variables: " + ", ".join(missing)
    try:
        port = int(values["DB_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        return values, "DB_PORT must be an integer between 1 and 65535"
    return values, None


def _run_pymysql(values: dict[str, str]) -> bool:
    try:
        import pymysql
    except ImportError as exc:
        print("PyMySQL test: FAILURE (dependency is not installed)")
        print(f"{type(exc).__name__}: {exc}")
        return False

    connection = None
    try:
        connection = pymysql.connect(
            host=values["DB_HOST"],
            port=int(values["DB_PORT"]),
            user=values["DB_USER"],
            password=values["DB_PASSWORD"],
            database=values["DB_NAME"],
            ssl={"ssl": True},
            **TIMEOUTS,
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), DATABASE()")
            version, database = cursor.fetchone()
        print(f"PyMySQL test: SUCCESS (server={version!s}, database={database!s})")
        return True
    except Exception as exc:
        print(f"PyMySQL test: FAILURE ({type(exc).__name__})")
        print(_safe_error(exc, values.get("DB_PASSWORD", "")))
        return False
    finally:
        if connection is not None:
            connection.close()


def _run_sqlalchemy(values: dict[str, str]) -> bool:
    try:
        from sqlalchemy import create_engine, text
    except ImportError as exc:
        print("SQLAlchemy test: FAILURE (dependency is not installed)")
        print(f"{type(exc).__name__}: {exc}")
        return False

    encoded_password = quote_plus(values["DB_PASSWORD"])
    url = (
        f"mysql+pymysql://{values['DB_USER']}:{encoded_password}"
        f"@{values['DB_HOST']}:{values['DB_PORT']}/{values['DB_NAME']}"
    )
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        pool_timeout=30,
        connect_args={"ssl": {"ssl": True}, **TIMEOUTS},
    )
    try:
        with engine.connect() as connection:
            version, database = connection.execute(
                text("SELECT VERSION(), DATABASE()")
            ).one()
        print(f"SQLAlchemy test: SUCCESS (server={version!s}, database={database!s})")
        return True
    except Exception as exc:
        print(f"SQLAlchemy test: FAILURE ({type(exc).__name__})")
        print(_safe_error(exc, values.get("DB_PASSWORD", "")))
        return False
    finally:
        engine.dispose()


def main() -> int:
    values, configuration_error = _configuration()
    if configuration_error:
        print(f"Configuration check: FAILURE ({configuration_error})")
        return 2

    print("Configuration check: SUCCESS (required values are present; values hidden)")
    print("SSL mode: enabled via PyMySQL ssl={'ssl': True}; no CA path is assumed")
    pymysql_ok = _run_pymysql(values)
    sqlalchemy_ok = _run_sqlalchemy(values)
    return 0 if pymysql_ok and sqlalchemy_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
