"""Career DNA snapshot timeline: save / list / delta / edit / delete.

The snapshot feature is meant to be used for YEARS, so the important behaviours
are (a) each snapshot is a frozen copy that later DNA edits cannot rewrite, and
(b) the delta against the previous chronological snapshot is what makes gradual
progress visible.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.core.database import get_db
from app.core.deps import _get_current_user
from app.models.career_dna import CareerDNA
from app.models.user import User


@pytest.fixture()
def app(db):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture()
def client(app, user):
    app.dependency_overrides[_get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture()
def dna(db, user):
    row = CareerDNA(
        user_id=user.id,
        interests=["robotics", "coding"],
        subjects=["maths"],
        skills=["coding"],
        values=["impact"],
        dna_filled=True,
    )
    db.add(row)
    db.commit()
    return row


def _snap(client, **body):
    return client.post("/api/v1/dna/snapshots", json=body)


# ------------------------------------------------------------------- save + list

def test_list_starts_empty(client):
    assert client.get("/api/v1/dna/snapshots").json() == []


def test_save_snapshot(client, dna):
    r = _snap(client, label="My DNA at 14", note="The curious kid who loves robots")
    assert r.status_code == 200, r.text
    snaps = r.json()
    assert len(snaps) == 1
    assert snaps[0]["label"] == "My DNA at 14"
    assert snaps[0]["note"] == "The curious kid who loves robots"


def test_save_with_no_dna_still_works_but_is_marked_unfilled(client, db):
    """A snapshot before onboarding exists must not 500 — it just records that
    there was nothing to capture yet."""
    r = _snap(client, label="Before DNA")
    assert r.status_code == 200
    assert r.json()[0]["dna_filled"] is False


def test_blank_label_gets_a_default(client, dna):
    snap = _snap(client, label="", note="x").json()[0]
    assert snap["label"].strip(), "label must never be blank"


def test_label_length_is_capped(client, dna):
    assert _snap(client, label="x" * 160).status_code == 200
    assert _snap(client, label="x" * 161).status_code == 422


def test_note_length_is_capped(client, dna):
    assert _snap(client, note="x" * 2000).status_code == 200
    assert _snap(client, note="x" * 2001).status_code == 422


# ------------------------------------------------------------------- immutability

def test_snapshot_is_frozen_when_later_dna_changes(client, db, dna):
    snap = _snap(client, label="My DNA at 14").json()[0]
    # the student "grows up": DNA is rewritten
    dna.interests = ["data science", "machine learning"]
    dna.skills = ["python"]
    db.commit()

    again = client.get("/api/v1/dna/snapshots").json()[0]
    assert again["interests"] == ["robotics", "coding"], "old snapshot was rewritten!"
    assert again["skills"] == ["coding"]
    assert snap["id"] == again["id"]


def test_two_snapshots_capture_two_different_moments(client, db, dna):
    first = _snap(client, label="My DNA at 14").json()[0]
    dna.interests = ["data science"]
    dna.subjects = ["data science"]
    db.commit()
    second = _snap(client, label="My DNA at 19").json()[-1]

    assert first["interests"] == ["robotics", "coding"]
    assert second["interests"] == ["data science"]
    assert second["id"] != first["id"]


# ------------------------------------------------------------------- delta

def test_first_snapshot_has_no_delta(client, dna):
    assert _snap(client, label="one").json()[0]["delta"] is None


def test_delta_shows_added_and_removed(client, db, dna):
    _snap(client, label="My DNA at 14")
    dna.interests = ["robotics", "AI"]     # dropped "coding", added "AI"
    dna.skills = ["python"]                # dropped "coding"
    db.commit()

    newest = _snap(client, label="My DNA at 19").json()[-1]
    delta = newest["delta"]
    assert delta["interests_added"] == ["AI"]
    assert delta["interests_removed"] == ["coding"]
    assert delta["skills_removed"] == ["coding"]
    assert delta["skills_added"] == ["python"]
    assert delta["subjects_added"] == []


def test_delta_is_computed_against_the_previous_snapshot_not_the_first(client, db, dna):
    _snap(client, label="at 14")            # interests: robotics, coding
    dna.interests = ["robotics", "AI"]
    db.commit()
    _snap(client, label="at 17")            # interests: robotics, AI
    dna.interests = ["robotics", "AI", "ML"]
    db.commit()
    newest = _snap(client, label="at 19").json()[-1]

    assert newest["delta"]["interests_added"] == ["ML"]
    assert newest["delta"]["interests_removed"] == [], "should diff vs age-17, not age-14"


def test_delta_recomputes_after_a_delete_merges_neighbours(client, db, dna):
    _snap(client, label="at 14")
    dna.interests = ["robotics", "AI"]
    db.commit()
    mid = _snap(client, label="at 17").json()[-1]
    dna.interests = ["robotics", "AI", "ML"]
    db.commit()
    _snap(client, label="at 19")

    client.delete(f"/api/v1/dna/snapshots/{mid['id']}")
    snaps = client.get("/api/v1/dna/snapshots").json()
    assert len(snaps) == 2
    # at 19 now diffs against at 14 directly
    assert snaps[-1]["delta"]["interests_added"] == ["AI", "ML"]


# ------------------------------------------------------------------- edit label/note

def test_edit_label_and_note_years_later(client, dna):
    sid = _snap(client, label="My DNA at 14", note="kid who loves robots").json()[0]["id"]
    r = client.patch(f"/api/v1/dna/snapshots/{sid}", json={
        "label": "My DNA at 14 (retro workshop)", "note": "revisited before uni"})
    assert r.status_code == 200
    mine = next(s for s in r.json() if s["id"] == sid)
    assert mine["label"] == "My DNA at 14 (retro workshop)"
    assert mine["note"] == "revisited before uni"


def test_edit_does_not_touch_the_frozen_dna(client, dna):
    sid = _snap(client, label="at 14").json()[0]["id"]
    before = client.get("/api/v1/dna/snapshots").json()[0]
    client.patch(f"/api/v1/dna/snapshots/{sid}", json={"label": "renamed", "note": "n"})
    after = next(s for s in client.get("/api/v1/dna/snapshots").json() if s["id"] == sid)
    for field in ("interests", "skills", "subjects", "values"):
        assert after[field] == before[field], f"{field} changed by an edit"


def test_partial_edit_leaves_other_field_alone(client, dna):
    sid = _snap(client, label="keep me", note="change me").json()[0]["id"]
    client.patch(f"/api/v1/dna/snapshots/{sid}", json={"note": "changed"})
    mine = next(s for s in client.get("/api/v1/dna/snapshots").json() if s["id"] == sid)
    assert mine["label"] == "keep me"
    assert mine["note"] == "changed"


def test_edit_validation_and_missing(client, dna):
    assert client.patch("/api/v1/dna/snapshots/999999", json={"label": "x"}).status_code == 404
    sid = _snap(client, label="ok").json()[0]["id"]
    assert client.patch(f"/api/v1/dna/snapshots/{sid}", json={"label": "x" * 161}).status_code == 422


# ------------------------------------------------------------------- delete

def test_delete_removes_it_and_reorders(client, dna):
    a = _snap(client, label="a").json()[0]
    b = _snap(client, label="b").json()[-1]
    assert client.delete(f"/api/v1/dna/snapshots/{a['id']}").status_code == 200
    left = client.get("/api/v1/dna/snapshots").json()
    assert [s["id"] for s in left] == [b["id"]]


def test_delete_missing_snapshot(client, dna):
    assert client.delete("/api/v1/dna/snapshots/999999").status_code == 404


# ------------------------------------------------------------------- isolation & auth

def test_snapshots_are_private_per_user(client, db, user, dna, app):
    """One student must never see, edit or delete another student's timeline."""
    mate = User(email="mate-snap@test.local", password_hash="x", grade=9)
    db.add(mate)
    db.commit()
    db.add(CareerDNA(user_id=mate.id, interests=["theirs"], dna_filled=True))
    db.commit()

    mine = _snap(client, label="mine").json()[0]["id"]

    app.dependency_overrides[_get_current_user] = lambda: mate
    mate_client = TestClient(app)
    assert mate_client.get("/api/v1/dna/snapshots").json() == []
    assert mate_client.patch(f"/api/v1/dna/snapshots/{mine}", json={"label": "stolen"}).status_code == 404
    assert mate_client.delete(f"/api/v1/dna/snapshots/{mine}").status_code == 404

    app.dependency_overrides[_get_current_user] = lambda: user
    assert client.get("/api/v1/dna/snapshots").json()[0]["label"] == "mine"


def test_endpoints_require_auth(app):
    """No token -> the router must not leak a timeline."""
    anon = TestClient(app)
    for method, path in [
        ("GET", "/api/v1/dna/snapshots"),
        ("POST", "/api/v1/dna/snapshots"),
        ("PATCH", "/api/v1/dna/snapshots/1"),
        ("DELETE", "/api/v1/dna/snapshots/1"),
    ]:
        r = anon.request(method, path, json={"label": "x"})
        assert r.status_code in (401, 403), (method, path, r.status_code)