"""Read-only smoke test: every GET the frontend warms must return 200.

Mirrors ROUTE_WARM in frontend/src/api.js so a broken route fails here rather
than as a blank panel in the browser. Auth-required, no mutations.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.core.database import get_db
from app.core.deps import _get_current_user


@pytest.fixture()
def client(db, user):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[_get_current_user] = lambda: user
    return TestClient(app)


# one entry per ROUTE_WARM list, flattened
WARM_PATHS = [
    # dashboard
    "/dashboard",
    # chat
    "/chat/conversations",
    # dna
    "/dna", "/dna/context",
    # careers
    "/careers?limit=50", "/careers/categories", "/careers/matches",
    # universities
    "/universities?limit=30", "/universities/filters", "/universities/recommended",
    # roadmap
    "/roadmap/tasks", "/roadmap/goals", "/roadmap/priorities", "/roadmap",
    # passport
    "/passport", "/passport/completion",
    # checkin
    "/checkins/current", "/checkins", "/checkins/graph",
    "/checkins/planner/day", "/checkins/graph?weeks=53",
    # profile
    "/auth/me", "/auth/links",
]


@pytest.mark.parametrize("path", WARM_PATHS)
def test_warmed_route_returns_200(client, path):
    r = client.get("/api/v1" + path)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("path", WARM_PATHS)
def test_warmed_route_returns_json_body(client, path):
    r = client.get("/api/v1" + path)
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() is not None