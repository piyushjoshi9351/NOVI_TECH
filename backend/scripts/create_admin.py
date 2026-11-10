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


def create_admin(
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    reset: bool = False,
) -> tuple[User, bool]:
    email = email.strip().lower()
    if not email:
        raise ValueError("Email is required")
    validate_new_password(password)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is not None:
            if not reset:
                raise ValueError(
                    f"An account with {email} already exists (role={existing.role.value}); "
                    "refusing to overwrite it. Use --reset to update the password and set role to admin."
                )
            existing.password_hash = hash_password(password)
            existing.role = UserRole.ADMIN
            existing.is_active = True
            if first_name.strip():
                existing.first_name = first_name.strip()
            if last_name.strip():
                existing.last_name = last_name.strip()
            db.commit()
            db.refresh(existing)
            return existing, False

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
        return user, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset a NOVI admin user")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", help="Password (prompted when omitted)")
    parser.add_argument("--first-name", default="", help="Optional first name")
    parser.add_argument("--last-name", default="", help="Optional last name")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Update password and promote to admin if the account already exists",
    )
    args = parser.parse_args()

    password = args.password
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1

    try:
        user, created = create_admin(
            args.email, password, args.first_name, args.last_name, reset=args.reset
        )
    except ValueError as exc:
        print(f"Could not create admin: {exc}", file=sys.stderr)
        return 1

    action_label = "Created" if created else "Updated"
    print(f"{action_label} admin user #{user.id} <{user.email}>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
