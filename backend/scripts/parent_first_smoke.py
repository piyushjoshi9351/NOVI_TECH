"""HTTP-only smoke harness. Run exclusively against a disposable test database.

Creates timestamped family fixtures and leaves them for inspection. It never
imports the configured DB, fabricates JWTs, deletes accounts, or prints secrets.
"""

import argparse
import json
from urllib.parse import urlsplit
import uuid

import httpx


def run(client, mode="flow"):
    stamp = uuid.uuid4().hex
    email = f"smoke.parent.{stamp}@example.com"
    child_email = f"smoke.child.{stamp}@example.com"
    initial = "Temporary-smoke-password"
    independent = "Independent-smoke-password"
    checks = 0

    def call(method, path, token=None, body=None, expected=200):
        nonlocal checks
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.request(method, "/api/v1" + path, headers=headers, json=body)
        assert response.status_code == expected, f"{method} {path}: expected {expected}, got {response.status_code}"
        checks += 1
        print(f"PASS: {method} {path}: {response.status_code}", flush=True)
        return response

    parent = call("POST", "/auth/parent/register", body={"name": "Smoke Parent", "email": email, "password": "Parent-smoke-password"}, expected=201).json()
    parent_token = parent["access_token"]
    assert parent["user"]["needs_child_setup"] is True
    child = call("POST", "/parent/students", parent_token, {"name": "Smoke Child", "email": child_email, "password": initial}, expected=201).json()
    sid, lid = child["student_id"], child["link_id"]
    assert child["status"] == "active" and child["scopes"] == ["basic"]
    assert not ({"password", "password_hash", "access_token", "token"} & set(child))
    assert initial not in json.dumps(child)
    assert call("GET", "/auth/me", parent_token).json()["needs_child_setup"] is False
    overview = call("GET", f"/parent/students/{sid}/overview", parent_token)
    assert overview.headers.get("cache-control") == "no-store"
    assert child_email not in overview.text and "password" not in overview.text
    assert set(overview.json()["student"]) == {"first_name", "grade"}
    for retired in ("/parent/links", "/parents/link"):
        call("POST", retired, parent_token, {"student_email": child_email}, expected=410)
    call("POST", "/auth/signup", body={"email": child_email, "password": initial}, expected=403)

    student = call("POST", "/auth/login", body={"email": child_email, "password": initial, "expected_role": "student"}).json()
    temporary_token = student["access_token"]
    assert student["user"]["must_change_password"] is True
    assert call("GET", "/auth/me", temporary_token).json()["must_change_password"] is True
    call("GET", "/dashboard", temporary_token, expected=403)
    call("GET", "/onboarding/flow", temporary_token, expected=403)
    changed = call("POST", "/auth/change-password", temporary_token, {"current_password": initial, "new_password": independent}).json()
    student_token = changed["access_token"]
    assert student_token != temporary_token and not changed["user"]["must_change_password"]
    call("GET", "/auth/me", temporary_token, expected=401)
    call("POST", "/auth/login", body={"email": child_email, "password": initial}, expected=401)
    assert call("GET", "/auth/me", student_token).json()["role"] == "student"
    flow = call("GET", "/onboarding/flow", student_token).json()
    assert flow["current"]["prefill"] == "Smoke Child"
    call("POST", "/auth/login", body={"email": child_email, "password": independent, "expected_role": "student"})
    call("GET", "/parent/students", student_token, expected=403)
    call("GET", "/dashboard", parent_token, expected=403)
    call("GET", "/parent/students/999999999/overview", parent_token, expected=404)
    call("POST", "/parent/students", parent_token, {"name": "Unchanged", "email": child_email, "password": "Never-replace-existing"}, expected=409)
    call("POST", "/parent/students", parent_token, {"name": "Second Child", "email": f"smoke.second.{stamp}@example.com", "password": initial}, expected=201)
    assert len(call("GET", "/parent/students", parent_token).json()["links"]) == 2

    assert call("GET", f"/parent/students/{sid}/insights", parent_token).json()["top_interests"] == []
    assert call("GET", f"/parent/students/{sid}/memory", parent_token).json()["growth"] is None
    if mode == "dashboard":
        call("PATCH", f"/student/parent-links/{lid}/scopes", student_token, {"insights": False, "memory": True})
        assert call("GET", f"/parent/students/{sid}/memory", parent_token).json()["growth"] is not None
        call("PATCH", f"/student/parent-links/{lid}/scopes", student_token, {"insights": False, "memory": False})
        assert call("GET", f"/parent/students/{sid}/memory", parent_token).json()["growth"] is None
    if mode == "application":
        for path in ("/student/parent-links", "/dna", "/dna/context", "/careers", "/careers/categories", "/careers/matches", "/universities", "/universities/filters", "/universities/recommended", "/roadmap", "/roadmap/tasks", "/roadmap/goals", "/roadmap/priorities", "/passport", "/passport/completion", "/checkins", "/checkins/current", "/checkins/graph", "/checkins/planner/day", "/chat/conversations", "/dashboard"):
            call("GET", path, student_token)
        item = call("POST", "/passport/items", student_token, {"category": "projects", "title": "Smoke website"}).json()
        call("DELETE", f"/passport/items/{item['id']}", student_token)
    call("POST", f"/student/parent-links/{lid}/approve", student_token, expected=409)
    call("POST", f"/student/parent-links/{lid}/revoke", student_token)
    call("GET", f"/parent/students/{sid}/overview", parent_token, expected=404)
    print(f"PASS: parent-first {mode} smoke ({checks} HTTP checks); no credentials printed", flush=True)
    return checks


def main(mode="flow"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    target = urlsplit(args.base_url)
    if target.hostname not in ("127.0.0.1", "localhost", "::1") or target.username or target.password:
        parser.error("Only a loopback test server is accepted; smoke checks create fixture rows")
    print("Disposable test DB required. These checks leave synthetic family fixtures.", flush=True)
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=60) as client:
        run(client, mode)
    return 0
