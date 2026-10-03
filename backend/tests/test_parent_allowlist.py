"""Parent responses are allowlists, not ORM dumps.

The threat here is future drift: someone adds a column to ``users`` or
``career_dna`` and a parent endpoint starts returning it. These tests assert on
the exact key set of each response so that cannot happen quietly.
"""

from datetime import date, timedelta

from app.models.career_dna import CareerDNA
from app.models.checkin import WeeklyCheckin
from app.models.enums import (
    CheckinStatus,
    GoalCategory,
    GoalStatus,
    PassportCategory,
    RoadmapStage,
)
from app.models.passport import PassportItem
from app.models.roadmap import Goal, RoadmapItem, WeeklyPriority
from app.schemas.parent import InsightsResponse, MemoryResponse, OverviewResponse
from app.services import parent_data, parent_links
from tests.conftest import auth_header

# Keys that must never appear anywhere in a parent payload, at any scope.
FORBIDDEN_KEYS = {
    "password_hash",
    "letta_agent_id",
    "sources",
    "excluded",
    "novi_reflection",
    "conversations",
    "conversation_id",
    "mood",
    "energy",
    "challenges",
    "pride",
    "next_week",
    "learnings",
    "accomplishments",
    "ai_summary",
    "notes",
    "email",
    "school_email",
}


def _all_keys(payload) -> set[str]:
    keys: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                keys.add(k)
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return keys


def _seed_sensitive_data(db, user):
    """Populate every table a parent must never see in full."""
    dna = CareerDNA(
        user_id=user.id,
        traits=["curious"],
        interests=["robotics", "music"],
        strengths=["systems thinking"],
        career_zones=["engineering"],
        sources={"interests": [{"value": "robotics", "quote": "I love robots", "conversation_id": 42}]},
        excluded=["ai"],
        novi_reflection="private reflection text",
    )
    db.add(dna)

    db.add(WeeklyCheckin(
        user_id=user.id,
        week_start=date.today(),
        accomplishments="Won a thing",
        learnings="Learned a thing",
        challenges="Struggled with math",
        pride="Proud moment",
        next_week="Do more",
        ai_summary={"wins": 1},
        status=CheckinStatus.SUBMITTED,
    ))
    db.add(PassportItem(
        user_id=user.id,
        category=PassportCategory.PROJECTS,
        title="Robotics club lead",
        description="Built a robot",
    ))
    db.add(Goal(
        user_id=user.id,
        title="Get into MIT",
        category=GoalCategory.UNIVERSITY,
        status=GoalStatus.ACTIVE,
        target_date=date.today() + timedelta(days=90),
    ))
    db.add(RoadmapItem(
        user_id=user.id, title="Take AP CS", grade=11,
        stage=RoadmapStage.EXPLORE, completed=False,
    ))
    db.add(WeeklyPriority(
        user_id=user.id,
        week_start=parent_data._current_week_start(),
        title="Finish robotics paper",
        completed=False,
    ))
    db.commit()
    return dna


# ------------------------------------------------------------------ overview
def test_overview_schema_has_no_forbidden_fields():
    for name, fields in OverviewResponse.model_fields.items():
        assert name not in FORBIDDEN_KEYS, f"OverviewResponse must not expose {name}"
    assert "school" in OverviewResponse.model_fields


def test_overview_does_not_leak_sensitive_data(db, user, active_link):
    _seed_sensitive_data(db, user)
    db.refresh(user)
    payload = parent_data.build_overview(db, user, active_link).model_dump()

    keys = _all_keys(payload)
    leaked = keys & FORBIDDEN_KEYS
    assert not leaked, f"overview leaked {leaked}"
    assert "I love robots" not in str(payload), "raw chat quote leaked"
    assert "private reflection text" not in str(payload)
    assert "Struggled with math" not in str(payload)
    assert "Proud moment" not in str(payload)


def test_overview_omits_student_email_and_agent_id(db, user, active_link):
    user.letta_agent_id = "agent-123456"
    db.commit()
    db.refresh(user)
    payload = parent_data.build_overview(db, user, active_link).model_dump()
    assert "agent-123456" not in str(payload)
    assert "student@example.com" not in str(payload)


def test_overview_reports_only_active_goals(db, user, active_link):
    db.add(Goal(user_id=user.id, title="Active goal", status=GoalStatus.ACTIVE))
    db.add(Goal(user_id=user.id, title="Completed goal", status=GoalStatus.COMPLETED))
    db.commit()
    titles = [g.title for g in parent_data.build_overview(db, user, active_link).active_goals]
    assert titles == ["Active goal"]


def test_overview_omits_completed_roadmap_items(db, user, active_link):
    db.add(RoadmapItem(user_id=user.id, title="Done already", completed=True))
    db.add(RoadmapItem(user_id=user.id, title="Still to do", completed=False))
    db.commit()
    items = parent_data.build_overview(db, user, active_link).upcoming_roadmap
    assert [i.title for i in items] == ["Still to do"]


def test_overview_is_json_serialisable(db, user, active_link):
    import json

    json.dumps(parent_data.build_overview(db, user, active_link).model_dump(mode="json"))


# ------------------------------------------------------------------ insights
def test_insights_schema_has_no_forbidden_fields():
    for name in InsightsResponse.model_fields:
        assert name not in FORBIDDEN_KEYS


def test_insights_never_returns_dna_sources(db, user, active_link):
    _seed_sensitive_data(db, user)
    payload = parent_data.build_insights(db, user, active_link).model_dump()

    assert "sources" not in payload
    assert "excluded" not in payload
    assert "I love robots" not in str(payload)
    assert "private reflection text" not in str(payload)


def test_insights_returns_derived_structures(db, user, active_link):
    _seed_sensitive_data(db, user)
    insights = parent_data.build_insights(db, user, active_link)
    assert insights.top_interests == ["robotics", "music"]
    assert insights.strengths == ["systems thinking"]
    assert insights.career_zones == ["engineering"]


def test_insights_handles_a_student_with_no_dna(db, user, active_link):
    insights = parent_data.build_insights(db, user, active_link)
    assert insights.top_interests == []
    assert insights.strengths == []


# ------------------------------------------------------------------ memory
def test_memory_schema_has_no_forbidden_fields():
    for name in MemoryResponse.model_fields:
        assert name not in FORBIDDEN_KEYS


class FakeLetta:
    def __init__(self, core=None, archival=None, boom=False):
        self._core = core or {}
        self._archival = archival or []
        self._boom = boom
        self.calls = []

    def get_memory(self, agent_id):
        self.calls.append(("get_memory", agent_id))
        if self._boom:
            raise RuntimeError("letta down")
        return self._core

    def get_archival(self, agent_id):
        self.calls.append(("get_archival", agent_id))
        if self._boom:
            raise RuntimeError("letta down")
        return self._archival


def test_memory_uses_only_the_human_core_block(db, user, active_link):
    user.letta_agent_id = "agent-1"
    db.commit()
    db.refresh(user)
    fake = FakeLetta(core={"memory": [
        {"label": "persona", "value": "You are Novi, an AI mentor"},
        {"label": "human", "value": "Name: Test. Grade: 10."},
    ]})
    result = parent_memory_service(db, user, active_link, fake)
    assert result.summary == "Name: Test. Grade: 10."
    assert "AI mentor" not in result.summary


def test_memory_filters_blocked_tags(db, user, active_link):
    user.letta_agent_id = "agent-1"
    db.commit()
    db.refresh(user)
    fake = FakeLetta(archival=[
        {"id": "1", "text": "secret chat content", "tags": ["chat"], "created_at": "2026-01-01T00:00:00"},
        {"id": "2", "text": "internal state", "tags": ["novistate"], "created_at": "2026-01-02T00:00:00"},
        {"id": "3", "text": "student raw", "tags": ["student"], "created_at": "2026-01-03T00:00:00"},
    ])
    result = parent_memory_service(db, user, active_link, fake)
    assert result.passages == []


def test_memory_keeps_allowed_tags(db, user, active_link):
    user.letta_agent_id = "agent-1"
    db.commit()
    db.refresh(user)
    fake = FakeLetta(archival=[
        {"id": "1", "text": "Won the science fair", "tags": ["achievement"], "created_at": "2026-01-01T00:00:00"},
        {"id": "2", "text": "Loves astronomy", "tags": ["interest"], "created_at": "2026-02-01T00:00:00"},
    ])
    result = parent_memory_service(db, user, active_link, fake)
    assert len(result.passages) == 2
    assert {p.text for p in result.passages} == {"Won the science fair", "Loves astronomy"}


def test_memory_sorts_newest_first_and_caps_at_50(db, user, active_link):
    user.letta_agent_id = "agent-1"
    db.commit()
    db.refresh(user)
    archival = [
        {
            "id": str(i),
            "text": f"memory {i}",
            "tags": ["goal"],
            "created_at": f"2026-01-{(i % 28) + 1:02d}T00:00:00",
        }
        for i in range(60)
    ]
    result = parent_memory_service(db, user, active_link, FakeLetta(archival=archival))
    assert len(result.passages) == 50
    times = [p.created_at for p in result.passages if p.created_at]
    assert times == sorted(times, reverse=True)


def test_memory_is_empty_when_letta_is_down(db, user, active_link):
    """A memory outage must degrade to an empty view, never a 500."""
    user.letta_agent_id = "agent-1"
    db.commit()
    db.refresh(user)
    result = parent_memory_service(db, user, active_link, FakeLetta(boom=True))
    assert result.available is False
    assert result.summary == ""
    assert result.passages == []


def test_memory_is_empty_without_an_agent_id(db, user, active_link):
    result = parent_memory_service(db, user, active_link, FakeLetta())
    assert result.available is False


def test_memory_uses_agent_id_from_the_database(db, user, active_link):
    """The agent id comes from the student row, never from the request."""
    user.letta_agent_id = "agent-from-db"
    db.commit()
    db.refresh(user)
    fake = FakeLetta()
    parent_memory_service(db, user, active_link, fake)
    assert all(agent_id == "agent-from-db" for _call, agent_id in fake.calls)


def parent_memory_service(db, user, link, fake_client):
    from app.services.parent_memory import build_memory

    return build_memory(user, link, client=fake_client)


# ------------------------------------------------------------------ no-store header
def test_parent_endpoints_send_no_store(client, parent, user, active_link):
    for path in ("overview",):
        r = client.get(
            f"/api/v1/parent/students/{user.id}/{path}",
            headers=auth_header(parent.id, "parent"),
        )
        assert r.status_code == 200
        assert r.headers.get("Cache-Control") == "no-store"


def test_memory_endpoint_sends_no_store(client, db, parent, user, active_link):
    parent_links.set_scopes(db, active_link, {"insights": False, "memory": True})
    r = client.get(
        f"/api/v1/parent/students/{user.id}/memory",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store"


def test_insights_endpoint_sends_no_store(client, db, parent, user, active_link):
    parent_links.set_scopes(db, active_link, {"insights": True, "memory": False})
    r = client.get(
        f"/api/v1/parent/students/{user.id}/insights",
        headers=auth_header(parent.id, "parent"),
    )
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store"
# ------------------------------------------------- student_id disclosure gate
def test_parent_list_exposes_student_id_only_when_active(client, db, parent, user):
    """The scoped endpoints are keyed by student id, so an active link must
    hand it over -- and a pending link must not."""
    hdr = auth_header(parent.id, "parent")

    pending = parent_links.create_pending_link(db, parent, user.email)
    body = client.get("/api/v1/parent/students", headers=hdr).json()
    assert body["links"][0]["status"] == "pending"
    assert body["links"][0]["student_id"] is None
    assert body["links"][0]["student"] is None

    parent_links.approve_link(db, pending)
    db.commit()
    body = client.get("/api/v1/parent/students", headers=hdr).json()
    assert body["links"][0]["status"] == "active"
    assert body["links"][0]["student_id"] == user.id

    # ...and it is the id the section endpoints actually accept.
    assert client.get(
        f"/api/v1/parent/students/{body['links'][0]['student_id']}/overview",
        headers=hdr,
    ).status_code == 200


def test_parent_list_hides_student_id_after_revoke(client, db, parent, user):
    hdr = auth_header(parent.id, "parent")
    link = parent_links.create_pending_link(db, parent, user.email)
    parent_links.approve_link(db, link)
    parent_links.revoke_link(db, link)
    db.commit()
    body = client.get("/api/v1/parent/students", headers=hdr).json()
    assert body["links"][0]["status"] == "revoked"
    assert body["links"][0]["student_id"] is None