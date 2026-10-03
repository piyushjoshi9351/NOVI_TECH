"""End-to-end smoke test against a RUNNING backend.

Unlike the pytest suite (which uses an in-process client and SQLite), this drives
the real app over HTTP against the real MySQL, so it exercises the router-level
authorization dependency, the migration-created cache table, the audit log line
and the actual JSON keys a browser receives.

Usage:
    ../venv/bin/python scripts/smoke_parent_dashboard.py [base_url]
"""

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"
STAMP = datetime.now().strftime("%H%M%S%f")

FORBIDDEN_KEYS = {
    "password_hash", "letta_agent_id", "sources", "excluded", "novi_reflection",
    "conversations", "conversation_id", "mood", "energy", "challenges", "pride",
    "next_week", "learnings", "accomplishments", "ai_summary", "notes", "email",
    "school_email", "summary", "passages", "text",
}

ok = fail = 0


def check(label, condition, detail=""):
    global ok, fail
    if condition:
        ok += 1
        print(f"  \033[32mPASS\033[0m {label}")
    else:
        fail += 1
        print(f"  \033[31mFAIL\033[0m {label} {detail}")


def call(method, path, token=None, body=None):
    """Return ``(status, body, headers)``.

    Header names are lower-cased: uvicorn emits them that way, and looking up
    ``Cache-Control`` in a plain dict is case-sensitive, so without this the
    no-store assertions silently pass on a response that has no such header.
    """
    req = urllib.request.Request(f"{API}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None

    def decode(raw):
        try:
            return json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return raw  # HTML/text error page; keep it for the failure message

    try:
        with urllib.request.urlopen(req, data, timeout=45) as r:
            return r.status, decode(r.read().decode()), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, decode(e.read().decode()), {k.lower(): v for k, v in e.headers.items()}


def cache_control(headers):
    return headers.get("cache-control", "")


def keys(node, acc=None):
    acc = acc if acc is not None else set()
    if isinstance(node, dict):
        for k, v in node.items():
            acc.add(k)
            keys(v, acc)
    elif isinstance(node, list):
        for i in node:
            keys(i, acc)
    return acc


print(f"\n=== parent dashboard smoke test @ {BASE} ===\n")

# ---------------------------------------------------------------- fixtures
print("setup")
# Student first: parent registration requires the student's email and creates the
# pending link as part of signup.
s_status, student, _ = call("POST", "/auth/signup", body={
    "email": f"smoke.child.{STAMP}@example.com",
    "password": "SmokeTest!2345",
    "first_name": "SmokeChild",
    "last_name": "PRIVATE_LAST_NAME",
    "role": "student",
    "grade": 11,
    "school": "Smoke High",
})
check("register student", s_status in (200, 201), f"-> {s_status} {student}")
if not isinstance(student, dict) or "access_token" not in student:
    print("\nsetup failed: cannot continue without a student token")
    sys.exit(1)
st = student["access_token"]
student_id = student["user"]["id"] if "user" in student else student["id"]

# Finish onboarding so there is real data to project. The conversational flow is
# not what we're testing, so skip it.
call("POST", "/onboarding/flow/skip", token=st, body={"step_id": "done"})

p_status, parent, _ = call("POST", "/auth/parent/register", body={
    "email": f"smoke.parent.{STAMP}@example.com",
    "password": "SmokeTest!2345",
    "first_name": "SmokeParent",
    "student_email": f"smoke.child.{STAMP}@example.com",
})
check("register parent (creates pending link)", p_status == 201, f"-> {p_status} {parent}")
if not isinstance(parent, dict) or "link_id" not in parent:
    print("\nsetup failed: parent registration did not return a link_id")
    sys.exit(1)
link_id = parent["link_id"]

# Parent signup returns no token by design; log in.
_, login, _ = call("POST", "/auth/login", body={
    "email": f"smoke.parent.{STAMP}@example.com",
    "password": "SmokeTest!2345",
})
check("parent login", isinstance(login, dict) and "access_token" in login, f"-> {login}")
pt = login["access_token"]

ls_status, links, _ = call("GET", "/parent/students", token=pt)
row = next((r for r in links["links"] if r["id"] == link_id), None)
check("link starts pending", row and row["status"] == "pending", f"-> {row}")
check("pending link hides student_id", row and row["student_id"] is None)
check("pending link hides student details", row and row["student"] is None)

# Unshared sections must be reachable while pending... no: pending is 404.
p_status, _, _ = call("GET", f"/parent/students/{student_id}/overview", token=pt)
check("pending link -> 404 on data endpoints", p_status == 404, f"-> {p_status}")

call("POST", f"/student/parent-links/{link_id}/approve", token=st)

# ---------------------------------------------------------------- basic only
print("\nbasic consent only")
call("PATCH", f"/student/parent-links/{link_id}/scopes", token=st,
     body={"insights": False, "memory": False})

for name, path in (("overview", "overview"), ("insights", "insights"), ("memory", "memory")):
    s, body, headers = call("GET", f"/parent/students/{student_id}/{path}", token=pt)
    check(f"{name}: 200 (not 403)", s == 200, f"-> {s} {body}")
    check(f"{name}: no-store", cache_control(headers) == "no-store", f"-> {cache_control(headers)!r}")
    leaked = keys(body) & FORBIDDEN_KEYS
    check(f"{name}: no forbidden keys", not leaked, f"leaked {sorted(leaked)}")

s, ov, _ = call("GET", f"/parent/students/{student_id}/overview", token=pt)
check("overview.basic present on basic grant", isinstance(ov, dict) and ov.get("basic") is not None)
check("last name never appears", "PRIVATE_LAST_NAME" not in json.dumps(ov))
check("grade is present", ov["student"]["grade"] == 11)
check("student ref is first name only", set(ov["student"].keys()) == {"first_name", "grade"})
check("passport is counts-only", set(ov["basic"]["passport"].keys()) == {"by_category", "total", "verified"})

s, ins, _ = call("GET", f"/parent/students/{student_id}/insights", token=pt)
check("insights scopes reflect basic only", ins["scopes"] == ["basic"], f"-> {ins['scopes']}")
check("insights is empty when unshared", ins["top_interests"] == [] and ins["novi_insight"] is None)

s, mem, _ = call("GET", f"/parent/students/{student_id}/memory", token=pt)
check("growth is null when unshared", mem["growth"] is None)

# ---------------------------------------------------------------- all granted
print("\nall sections granted")
call("PATCH", f"/student/parent-links/{link_id}/scopes", token=st,
     body={"insights": True, "memory": True})

t0 = time.time()
s, ins, _ = call("GET", f"/parent/students/{student_id}/insights", token=pt)
first_ms = int((time.time() - t0) * 1000)
check("insights 200 with all scopes", s == 200 and sorted(ins["scopes"]) == ["basic", "insights", "memory"],
      f"-> {ins.get('scopes')}")
# A provider outage is legitimately allowed to fall back to the deterministic
# template, so "some insight" is the contract -- not "an LLM produced it".
check("insight text produced", bool(ins["novi_insight"]), "-> empty")
print(f"       (insight call {first_ms}ms)")

t0 = time.time()
s, ins2, _ = call("GET", f"/parent/students/{student_id}/insights", token=pt)
cached_ms = int((time.time() - t0) * 1000)
check("insight is cached (identical text)", ins2["novi_insight"] == ins["novi_insight"])
print(f"       (cached call {cached_ms}ms)")
if ins["novi_insight"]:
    check("cached call is faster", cached_ms <= max(first_ms, 250),
          f"{cached_ms}ms vs {first_ms}ms")

s, mem, _ = call("GET", f"/parent/students/{student_id}/memory", token=pt)
check("growth object present", mem["growth"] is not None)
if mem["growth"]:
    g = mem["growth"]
    check("growth has no passage text", "passages" not in g and "summary" not in g)
    check("growth keys are a known subset",
          set(g.keys()) <= {"completed_milestones", "strength_trend",
                            "milestones_completed", "trend_change"},
          f"-> {set(g.keys())}")
    # These are the sensitive ones: assert the VALUES are never free text.
    check("milestone text is not passage-like",
          all(isinstance(m, dict) for m in (g.get("completed_milestones") or [])),
          f"-> {g.get('completed_milestones')}")
    check("last name never appears in growth", "PRIVATE_LAST_NAME" not in json.dumps(g))
    print(f"       (growth: {len(g.get('completed_milestones') or [])} milestones, "
          f"{len(g.get('strength_trend') or [])} trend points)")

# ---------------------------------------------------------------- revocation
print("\nrevocation is immediate")
call("PATCH", f"/student/parent-links/{link_id}/scopes", token=st,
     body={"insights": True, "memory": False})
s, mem, _ = call("GET", f"/parent/students/{student_id}/memory", token=pt)
check("revoked section -> null right away", mem["growth"] is None)
s, ins3, _ = call("GET", f"/parent/students/{student_id}/insights", token=pt)
check("revoking memory changes the insight cache key",
      ins3["novi_insight"] != ins["novi_insight"],
      "-> insight text unchanged, so it may have been served from the old key")

# ---------------------------------------------------------------- authz
print("\nauthorization")
# Parent sign-up does not hand back a token, so register then log in.
_, other, _ = call("POST", "/auth/parent/register", body={
    "email": f"smoke.other.{STAMP}@example.com",
    "password": "SmokeTest!2345",
    "first_name": "OtherParent",
    "student_email": f"smoke.other.child.{STAMP}@example.com",
})
_, ologin, _ = call("POST", "/auth/login", body={
    "email": f"smoke.other.{STAMP}@example.com",
    "password": "SmokeTest!2345",
})
check("other parent logs in", isinstance(ologin, dict) and "access_token" in ologin, f"-> {ologin}")
ot = ologin["access_token"]
s, _, _ = call("GET", f"/parent/students/{student_id}/overview", token=ot)
check("foreign student_id -> 404", s == 404, f"-> {s}")

s, _, _ = call("GET", f"/parent/students/{student_id}/overview")
check("no token -> 401", s == 401, f"-> {s}")

call("POST", f"/student/parent-links/{link_id}/revoke", token=st)
s, _, _ = call("GET", f"/parent/students/{student_id}/overview", token=pt)
check("revoked link -> 404 immediately", s == 404, f"-> {s}")

_, links, _ = call("GET", "/parent/students", token=pt)
row = next((r for r in links["links"] if r["id"] == link_id), {})
check("revoked link hides student_id in the list", row.get("student_id") is None)

# ---------------------------------------------------------------- advisor
print("\nparent advisor")
_, link2, _ = call("POST", "/parent/links", token=pt,
                   body={"student_email": f"smoke.child.{STAMP}@example.com"})
check("re-link after revoke", isinstance(link2, dict) and "link_id" in link2, f"-> {link2}")
call("POST", f"/student/parent-links/{link2['link_id']}/approve", token=st)

s, a, ah = call("POST", "/parents/advisor", token=pt,
                body={"question": "What are they into?", "child_id": student_id})
check("advisor answers", s == 200 and bool(a.get("answer")), f"-> {s} {a}")
check("advisor is no-store", cache_control(ah) == "no-store", f"-> {cache_control(ah)!r}")
if a.get("answer"):
    check("advisor answer omits last name", "PRIVATE_LAST_NAME" not in a["answer"])
    check("advisor answer is bounded", len(a["answer"]) <= 800, f"-> {len(a['answer'])} chars")

s, _, _ = call("POST", "/parents/advisor", token=pt, body={"question": "x" * 5000})
check("over-length question -> 422", s == 422, f"-> {s}")

# Use a FRESH parent: the limit is a 60s sliding window, and the LLM-backed calls
# above are slow enough that their timestamps age out mid-burst, which makes a
# shared-parent assertion flaky. A clean counter trips deterministically.
_, rparent, _ = call("POST", "/auth/parent/register", body={
    "email": f"smoke.rate.{STAMP}@example.com",
    "password": "SmokeTest!2345",
    "first_name": "RateParent",
    "student_email": f"smoke.child.{STAMP}@example.com",
})
_, rlogin, _ = call("POST", "/auth/login", body={
    "email": f"smoke.rate.{STAMP}@example.com",
    "password": "SmokeTest!2345",
})
rt = rlogin["access_token"]
_, rlink, _ = call("POST", "/parent/links", token=rt,
                   body={"student_email": f"smoke.child.{STAMP}@example.com"})
if isinstance(rlink, dict) and "link_id" in rlink:
    call("POST", f"/student/parent-links/{rlink['link_id']}/approve", token=st)

t0 = time.time()
codes = []
for _ in range(30):  # limit is 20/min; stop at the first rejection
    code = call("POST", "/parents/advisor", token=rt, body={"question": "hi"})[0]
    codes.append(code)
    if code == 429:
        break
check("advisor rate limit -> 429", 429 in codes,
      f"-> no 429 in {len(codes)} calls over {time.time() - t0:.1f}s")
if 429 in codes:
    check("limiter allows at most 20 before rejecting", codes.index(429) <= 20,
          f"-> tripped at {codes.index(429)}")

print(f"\n=== {ok} passed, {fail} failed ===\n")
sys.exit(1 if fail else 0)