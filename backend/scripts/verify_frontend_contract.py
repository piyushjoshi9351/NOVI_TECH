"""Static contract check between the Next.js frontend and the FastAPI backend.

The frontend has no test runner, so this asserts the things that would otherwise
only fail in a browser:

  1. every endpoint the new parent/student views call really exists;
  2. every response field they read really exists in that schema;
  3. nothing in the frontend references letta_agent_id or talks to Letta;
  4. the parent area never requests chat/conversation data;
  5. the two auth screens post to the endpoints the backend actually exposes.

Run from the backend directory:  python -X utf8 scripts/verify_frontend_contract.py
"""

import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND = BACKEND.parent / "frontend"

sys.path.insert(0, str(BACKEND))
from app.main import app  # noqa: E402

SPEC = app.openapi()
SCHEMAS = SPEC["components"]["schemas"]
FAILS: list[str] = []
WARNS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"  [FAIL] {msg}")


def warn(msg: str) -> None:
    WARNS.append(msg)
    print(f"  [WARN] {msg}")


def ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


# ---------------------------------------------------------------- helpers
def resolve(schema_name: str, depth: int = 0):
    """Follow $ref / allOf to a concrete schema, or None."""
    if depth > 6 or not schema_name:
        return None
    s = SCHEMAS.get(schema_name)
    if not s:
        return None
    for key in ("allOf", "anyOf", "oneOf"):
        if key in s:
            for part in s[key]:
                ref = part.get("$ref")
                if ref:
                    got = resolve(ref.split("/")[-1], depth + 1)
                    if got:
                        return got
    return s


def success_schema(path: str, method: str):
    op = SPEC["paths"].get(path, {}).get(method)
    if not op:
        return None
    for code, resp in op.get("responses", {}).items():
        if code.startswith("2"):
            return resp.get("content", {}).get("application/json", {}).get("schema")
    return None


def top_level_fields(path: str, method: str) -> set[str]:
    schema = success_schema(path, method)
    if not schema:
        return set()
    ref = schema.get("$ref")
    if ref:
        schema = resolve(ref.split("/")[-1]) or {}
    if schema.get("type") == "array":
        ref = schema.get("items", {}).get("$ref")
        if ref:
            schema = resolve(ref.split("/")[-1]) or {}
    return set((schema or {}).get("properties", {}).keys())


API_PREFIX = "/api/v1"  # src/api.js prepends this to every path


def strip_comments(text: str) -> str:
    """Drop // and /* */ comments so prose about letta_agent_id isn't a hit."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def source_files(patterns):
    out = []
    for pat in patterns:
        out.extend(sorted(FRONTEND.glob(pat)))
    return [p for p in out if "node_modules" not in p.parts and ".next" not in p.parts]


def normalise(path_expr: str) -> str:
    """`/parent/students/${studentId}/overview` -> the backend's real path."""
    # The client prepends the version prefix, so the UI writes `/parent/...`.
    expr = API_PREFIX + path_expr.split("?")[0]
    # Collapse both ${...} interpolation and a literal {id} to one placeholder.
    path = re.sub(r"\$\{[^}]+\}", "{p0}", expr)
    path = re.sub(r"\{[^}/]+\}", "{p0}", path)
    return re.sub(r"/+$", "", path) or "/"


def real_path(expr: str):
    norm = normalise(expr)
    if norm in SPEC["paths"]:
        return norm
    # The frontend uses a concrete id where the backend declares a placeholder.
    pattern = re.escape(norm).replace(re.escape("{p0}"), r"\{[^/]+\}")
    for candidate in SPEC["paths"]:
        if re.fullmatch(pattern, candidate):
            return candidate
    return None


# ---------------------------------------------------- 1. endpoints exist
print("\n1. Endpoints called by the parent feature")
PARENT_CALLS = [
    ("src/views/parent/ParentDashboard.jsx", "GET", "/parent/students"),
    ("src/views/parent/ParentDashboard.jsx", "POST", "/parent/links"),
    ("src/views/parent/ParentStudent.jsx", "GET", "/parent/students"),
    ("src/views/student/ParentAccess.jsx", "GET", "/student/parent-links"),
    ("src/views/student/ParentAccess.jsx", "PATCH", "/student/parent-links/{id}/scopes"),
    ("src/views/student/ParentAccess.jsx", "POST", "/student/parent-links/{id}/approve"),
    ("src/views/student/ParentAccess.jsx", "POST", "/student/parent-links/{id}/revoke"),
    ("src/views/AuthPage.jsx", "POST", "/auth/parent/register"),
    ("src/views/AuthPage.jsx", "POST", "/auth/signup"),
    ("src/views/AuthPage.jsx", "POST", "/auth/login"),
    ("src/site-auth/AuthShell.tsx", "POST", "/auth/parent/register"),
    ("src/site-auth/AuthShell.tsx", "POST", "/auth/signup"),
    ("src/site-auth/AuthShell.tsx", "POST", "/auth/login"),
    ("src/site-auth/AuthShell.tsx", "GET", "/auth/me"),
    ("src/auth.jsx", "GET", "/auth/me"),
]
for rel, method, expr in PARENT_CALLS:
    real = real_path(expr)
    if not real:
        fail(f"{rel} calls {method} {expr} which the backend does not expose")
    elif method.lower() not in SPEC["paths"][real]:
        fail(f"{rel} calls {method} {expr} but the backend only supports "
             f"{sorted(k.upper() for k in SPEC['paths'][real])}")
    else:
        ok(f"{method} {expr} -> {real}")

print("\n1b. The three sections the parent page renders")
for section in ("overview", "insights", "memory"):
    real = real_path(f"/parent/students/{{sid}}/{section}")
    if not real:
        fail(f"/parent/students/<id>/{section} does not exist")
    else:
        ok(f"/parent/students/<id>/{section} exists -> {real}")

# --------------------------------------------- 2. response fields are real
print("\n2. Response fields the parent views read")
FIELD_EXPECTATIONS = [
    ("GET", "/parent/students", {"links"}),
    ("GET", "/parent/students/{id}/overview", {
        "student", "scopes", "school", "active_goals", "recent_passport",
        "upcoming_roadmap", "this_week",
    }),
    ("GET", "/parent/students/{id}/insights", {
        "student", "scopes", "top_interests", "strengths", "career_zones",
        "top_career_matches", "profile_strength", "university_readiness",
    }),
    ("GET", "/parent/students/{id}/memory", {
        "student", "scopes", "summary", "passages", "available",
    }),
    ("GET", "/student/parent-links", {"links"}),
]
for method, path, wanted in FIELD_EXPECTATIONS:
    real = real_path(path)
    fields = top_level_fields(real, method.lower()) if real else set()
    if not fields:
        fail(f"{method} {path} has no declared response schema")
        continue
    missing = sorted(wanted - fields)
    if missing:
        fail(f"{method} {path} is missing {missing}")
    else:
        ok(f"{method} {path} exposes all {len(wanted)} fields the UI reads")

# link row fields, read by both dashboards
link_row = resolve("ParentLinkOut") or {}
row_fields = set(link_row.get("properties", {}))
for needed in ("id", "status", "label", "scopes", "student", "student_id"):
    if needed not in row_fields:
        fail(f"ParentLinkOut is missing `{needed}`, which the switcher needs")
    else:
        ok(f"ParentLinkOut.{needed} exists")
if "student_id" not in row_fields:
    warn("without ParentLinkOut.student_id the parent UI cannot address a child")

stu_row = resolve("StudentLinkOut") or {}
for needed in ("id", "status", "label", "scopes", "parent_name"):
    if needed not in set(stu_row.get("properties", {})):
        fail(f"StudentLinkOut is missing `{needed}`")

# ------------------------------------------------- 3. no Letta leakage
print("\n3. No Letta or agent-id leakage in the frontend")
BANNED = ["letta_agent_id", "letta_agent", "/letta", "LETTA_BASE", "LETTA_API"]
files = source_files(["src/**/*.js", "src/**/*.jsx", "src/**/*.ts", "src/**/*.tsx",
                      "app/**/*.js", "app/**/*.jsx", "app/**/*.ts", "app/**/*.tsx"])
hits = []
for f in files:
    text = strip_comments(f.read_text(encoding="utf-8"))
    for needle in BANNED:
        if needle in text:
            hits.append(f"{f.relative_to(FRONTEND)} references {needle}")
if hits:
    for h in hits:
        fail(h)
else:
    ok(f"none of {len(BANNED)} forbidden identifiers appear in {len(files)} source files")

# ------------------------------------- 4. parent area never reads raw chat
print("\n4. The parent area never requests chat or conversation data")
CHAT = ["/chat", "conversation", "messages", "streamChat"]
parent_files = [
    FRONTEND / "src/views/parent/ParentDashboard.jsx",
    FRONTEND / "src/views/parent/ParentStudent.jsx",
    FRONTEND / "src/views/student/ParentAccess.jsx",
]
for f in parent_files:
    if not f.exists():
        fail(f"missing {f}")
        continue
    text = strip_comments(f.read_text(encoding="utf-8"))
    bad = [n for n in CHAT if n in text]
    if bad:
        fail(f"{f.name} references {bad}")
    else:
        ok(f"{f.name} touches no chat/conversation endpoint")

# ------------------------------------------- 5. signup is student-only
print("\n5. Client code never asks for a parent role from /auth/signup")
for f in (FRONTEND / "src/views/AuthPage.jsx", FRONTEND / "src/site-auth/AuthShell.tsx"):
    text = strip_comments(f.read_text(encoding="utf-8"))
    # `expected_role: role` is the login guard and is fine; a bare `role: role`
    # on a signup body would be the bug the backend now rejects.
    bad = re.findall(r"(?<![\w_])role:\s*role\b", text)
    if bad:
        fail(f"{f.name} still posts the selected tab as role ({len(bad)}x)")
    else:
        ok(f"{f.name} never posts a variable role to signup")

print("\n" + "=" * 62)
if FAILS:
    print(f"FAILED ({len(FAILS)}):")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("FRONTEND CONTRACT OK" + (f" ({len(WARNS)} warnings)" if WARNS else ""))
if WARNS:
    for w in WARNS:
        print("  ~", w)