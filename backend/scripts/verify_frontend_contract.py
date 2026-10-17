"""Read-only Next.js/FastAPI parent-first contract checks. No DB connection."""
from pathlib import Path
import re
import sys

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
sys.path.insert(0, str(BACKEND))
from app.main import app


def main():
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    checks = 0

    def check(condition, label):
        nonlocal checks
        if not condition:
            raise AssertionError(label)
        checks += 1
        print(f"PASS: {label}")

    endpoints = {
        "/auth/parent/register": ("post",), "/auth/login": ("post",),
        "/auth/change-password": ("post",), "/auth/me": ("get",),
        "/parent/students": ("get", "post"),
        "/parent/students/{student_id}/overview": ("get",),
        "/parent/students/{student_id}/insights": ("get",),
        "/parent/students/{student_id}/memory": ("get",),
        "/student/parent-links": ("get",),
        "/student/parent-links/{link_id}/scopes": ("patch",),
        "/student/parent-links/{link_id}/revoke": ("post",),
        "/student/parent-links/{link_id}/approve": ("post",),  # Legacy pending only.
        "/parents/advisor": ("post",),
    }
    for path, methods in endpoints.items():
        check(all(method in spec["paths"].get("/api/v1" + path, {}) for method in methods), f"endpoint contract: {path}")
    for name, wanted in {
        "ParentRegisterRequest": {"name", "email", "password"},
        "ParentStudentCreate": {"name", "email", "password"},
        "ParentStudentCreated": {"student_id", "link_id", "name", "status", "scopes", "activated_at"},
        "MeResponse": {"role", "must_change_password", "needs_child_setup", "has_local_password"},
        "PasswordChangeResponse": {"access_token", "user"},
        "ParentLinkOut": {"account_state", "student", "student_id", "status", "scopes"},
        "OverviewResponse": {"student", "scopes", "basic"},
        "MemoryResponse": {"student", "scopes", "growth"},
        "StudentLinkOut": {"parent_name", "activation_source", "can_manage", "can_approve", "scopes"},
    }.items():
        check(wanted <= set(schemas[name]["properties"]), f"response/request fields: {name}")
    check(set(schemas["ParentRegisterRequest"]["properties"]) == {"name", "email", "password"}, "parent registration has no child-email or role input")
    check(not ({"password", "password_hash", "access_token"} & set(schemas["ParentStudentCreated"]["properties"])), "child receipt cannot leak passwords or tokens")
    files = [path for directory in ("src", "app") for path in (FRONTEND / directory).rglob("*") if path.suffix in (".js", ".jsx", ".ts", ".tsx")]
    for path in files:
        source = path.read_text(encoding="utf-8")
        check(not re.search(r"[\"'`](/parent/links|/parents/link|/auth/links)(?:[\"'`?])", source), f"no retired call: {path.relative_to(FRONTEND)}")
        if "/views/parent/" in path.as_posix():
            check(not re.search(r"api\([\"'`]\/(?:chat|memory|checkins)(?:\/|[\"'`])", source), f"parent view uses scoped data: {path.name}")
    auth_shell = FRONTEND / "src/site-auth/AuthShell.tsx"
    check("useAuthForm" in auth_shell.read_text(encoding="utf-8"), "public auth shell uses shared auth form")
    check(sum(path.read_text(encoding="utf-8").count("<AuthProvider>") for path in files) == 1, "one AuthProvider")
    for path in ("app/(app)/first-login/page.jsx", "app/(app)/parent/add-child/page.jsx", "app/(app)/parent/settings/page.jsx"):
        check((FRONTEND / path).is_file(), f"setup/settings route: {path}")
    print(f"FRONTEND CONTRACT OK ({checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
