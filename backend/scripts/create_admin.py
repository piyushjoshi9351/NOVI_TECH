"""Create a NOVI admin account.

Admin signup is intentionally closed. This is the only supported way to create
the first admin user.

Usage (from backend/):
    python scripts/create_admin.py --email admin@example.com
    python scripts/create_admin.py --email admin@example.com --password '...'

If --password is omitted the script prompts without echoing the value.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.passwords import validate_new_password


def create_admin(email: str, password: str, first_name: str = "", last_name: str = "") -> User:
    email = email.strip().lower()
    if not email:
        raise ValueError("Email is required")
    validate_new_password(password)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise ValueError(
                f"An account with {email} already exists (role={existing.role.value}); "
                "refusing to overwrite it."
            )
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a NOVI admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", help="Password (prompted when omitted)")
    parser.add_argument("--first-name", default="", help="Optional first name")
    parser.add_argument("--last-name", default="", help="Optional last name")
    args = parser.parse_args()

    password = args.password
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1

    try:
        user = create_admin(args.email, password, args.first_name, args.last_name)
    except ValueError as exc:
        print(f"Could not create admin: {exc}", file=sys.stderr)
        return 1

    print(f"Created admin user #{user.id} <{user.email}>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
