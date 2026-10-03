"""End-to-end smoke test of the parent consent flow against the REAL engine.

Unlike the pytest suite (in-memory SQLite) this exercises the actual FastAPI app,
routers, dependencies and MySQL. It creates its own throwaway rows and deletes
them in a finally block.

Usage:  python -X utf8 scripts/smoke_parent_flow.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import ParentStudentLink, User  # noqa: E402

PARENT = "smoke_parent@novi-smoke.example.com"
STUDENT = "smoke_student@novi-smoke.example.com"

FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -> ' + detail) if detail and not ok else ''}")
    if not ok:
        FAILS.append(label)


def cleanup() -> None:
    with SessionLocal() as db:
        db.query(ParentStudentLink).filter(
            ParentStudentLink.invited_email.in_([PARENT, STUDENT, "ghost@novi-smoke.example.com"])
        ).delete(synchronize_session=False)
        db.query(User).filter(User.email.in_([PARENT, STUDENT, "ghost@novi-smoke.example.com"])).delete(
            synchronize_session=False
        )
        db.commit()


def main() -> int:
    cleanup()
    # NOTE: lifespan is intentionally not started -- schema is already migrated.
    client = TestClient(app)

    try:
        print("\n1. Student signs up (self-service)")
        r = client.post("/api/v1/auth/signup", json={
            "email": STUDENT, "password": "hunter2!",
            "name": "Smoke", "last_name": "Student", "grade": 11,
        })
        check("student signup", r.status_code == 200, r.text[:200])
        student_token = r.json()["access_token"]
        student_id = r.json()["user"]["id"]

        print("\n2. Parent registers and requests to follow the student")
        r = client.post("/api/v1/auth/parent/register", json={
            "email": PARENT, "password": "hunter2!",
            "name": "Smoke", "student_email": STUDENT,
        })
        check("parent register", r.status_code == 201, r.text[:300])
        link_id = r.json()["link_id"]
        check("message is the generic one", "sent them a request" in r.json()["message"])
        check("register does not mint a session", "access_token" not in r.json())

        r = client.post("/api/v1/auth/login", json={
            "email": PARENT, "password": "hunter2!", "expected_role": "parent"})
        check("parent login with expected_role", r.status_code == 200, r.text[:300])
        parent_token = r.json()["access_token"]
        check("login reports role parent", r.json()["user"]["role"] == "parent")

        r = client.post("/api/v1/auth/login", json={
            "email": PARENT, "password": "hunter2!", "expected_role": "student"})
        check("wrong expected_role is refused", r.status_code == 403)

        ph = {"Authorization": f"Bearer {parent_token}"}
        sh = {"Authorization": f"Bearer {student_token}"}

        print("\n3. Pending link grants the parent nothing")
        check("parent overview blocked", client.get(
            f"/api/v1/parent/students/{student_id}/overview", headers=ph).status_code == 404)
        check("parent insights blocked", client.get(
            f"/api/v1/parent/students/{student_id}/insights", headers=ph).status_code == 404)

        print("\n4. The student sees and approves the request")
        r = client.get("/api/v1/student/parent-links", headers=sh)
        check("student sees the pending link", r.status_code == 200 and len(r.json()["links"]) == 1)
        check("parent name is shown", r.json()["links"][0]["parent_name"].startswith("Smoke"))

        r = client.patch(f"/api/v1/student/parent-links/{link_id}/scopes",
                         json={"insights": True, "memory": False}, headers=sh)
        check("student grants insights", r.status_code == 200
              and set(r.json()["scopes"]) == {"basic", "insights"}, r.text[:200])

        r = client.post(f"/api/v1/student/parent-links/{link_id}/approve", headers=sh)
        check("approve -> active", r.status_code == 200 and r.json()["status"] == "active")

        print("\n5. Now the parent can read the granted scopes")
        r = client.get(f"/api/v1/parent/students/{student_id}/overview", headers=ph)
        check("overview allowed", r.status_code == 200, r.text[:300])
        check("overview is no-store", r.headers.get("Cache-Control") == "no-store")
        check("overview exposes no email", STUDENT not in r.text)

        r = client.get(f"/api/v1/parent/students/{student_id}/insights", headers=ph)
        check("insights allowed", r.status_code == 200, r.text[:200])

        r = client.get(f"/api/v1/parent/students/{student_id}/memory", headers=ph)
        check("memory denied (not granted)", r.status_code == 403)

        print("\n6. /auth/me reports the DB role")
        r = client.get("/api/v1/auth/me", headers=ph)
        check("parent /me role", r.status_code == 200 and r.json()["role"] == "parent")
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {parent_token}"})
        check("no letta_agent_id leak", "letta_agent_id" not in r.json())

        print("\n7. IDOR: parent cannot read another student")
        r = client.get("/api/v1/parent/students/999999/overview", headers=ph)
        check("unknown student -> 404", r.status_code == 404)

        print("\n8. Revoke kills access immediately")
        r = client.post(f"/api/v1/student/parent-links/{link_id}/revoke", headers=sh)
        check("revoke", r.status_code == 200 and r.json()["status"] == "revoked")
        check("overview blocked after revoke", client.get(
            f"/api/v1/parent/students/{student_id}/overview", headers=ph).status_code == 404)

        print("\n9. Invitation for an email with no account")
        r = client.post("/api/v1/parent/links",
                        json={"student_email": "ghost@novi-smoke.example.com"}, headers=ph)
        check("invite for unknown email", r.status_code == 201, r.text[:200])
        check("same generic message", "sent them a request" in r.json()["message"])
        ghost_link = r.json()["link_id"]

        r = client.post("/api/v1/auth/signup", json={
            "email": "ghost@novi-smoke.example.com", "password": "hunter2!", "role": "student"})
        check("ghost signs up", r.status_code == 200, r.text[:200])

        with SessionLocal() as db:
            link = db.scalar(select(ParentStudentLink).where(ParentStudentLink.id == ghost_link))
            check("invitation resolved to the new account", link.student_id is not None)
            check("resolution did NOT auto-activate", link.status.value == "pending")
            check("only a hash is stored", link.invite_token_hash and len(link.invite_token_hash) == 64)

        print("\n10. Legacy /parents/* is consent-gated too")
        r = client.get("/api/v1/parents/dashboard", headers=ph)
        check("legacy dashboard still works", r.status_code == 200, r.text[:200])
        check("revoked child absent from legacy dashboard",
              all(c["name"] != "Smoke Student" for c in r.json().get("children", [])))

    finally:
        client.close()
        cleanup()

    print("\n" + "=" * 60)
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())