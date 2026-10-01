"""Contribution-graph correctness: a day must light up exactly when checked in."""
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router
from app.core.database import get_db
from app.core.deps import _get_current_user
from app.models.chat import Conversation, Message
from app.models.checkin import WeeklyCheckin
from app.models.enums import CheckinStatus, MessageRole
from app.models.planner import DailyCheckin, ScheduleBlock
from app.services.checkins import contribution_graph


@pytest.fixture()
def client(db, user):
    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[_get_current_user] = lambda: user
    return TestClient(app)


def _cells(graph):
    return {c["date"]: c for w in graph["weeks"] for c in w["days"]}


def _add_daily(db, user, day, **fields):
    db.add(DailyCheckin(user_id=user.id, date=day, **fields))
    db.commit()


def test_grid_shape_is_weeks_by_seven_mondays(db, user):
    graph = contribution_graph(db, user, weeks=10)
    assert len(graph["weeks"]) == 10
    for week in graph["weeks"]:
        assert len(week["days"]) == 7
        assert date.fromisoformat(week["week_start"]).weekday() == 0


def test_empty_history_is_all_level_zero(db, user):
    cells = _cells(contribution_graph(db, user))
    assert cells
    assert all(c["level"] == 0 and c["kind"] == "" for c in cells.values())
    assert contribution_graph(db, user)["stats"]["active_days"] == 0


def test_daily_checkin_greens_only_that_day(db, user):
    day = date.today()
    _add_daily(db, user, day, focus="Ship heatmap", mood="great", energy=8, status=CheckinStatus.SUBMITTED)

    cells = _cells(contribution_graph(db, user))
    assert cells[day.isoformat()]["level"] > 0
    assert cells[day.isoformat()]["kind"] == "check-in"

    neighbours = [day - timedelta(days=1), day + timedelta(days=1)]
    for n in neighbours:
        if n.isoformat() in cells:
            assert cells[n.isoformat()]["level"] == 0


def test_blank_draft_stays_grey(db, user):
    day = date.today()
    _add_daily(db, user, day, status=CheckinStatus.DRAFT)
    cells = _cells(contribution_graph(db, user))
    assert cells[day.isoformat()]["level"] == 0


def test_more_fields_means_darker_cell(db, user):
    light = date.today() - timedelta(days=3)
    heavy = date.today() - timedelta(days=2)
    _add_daily(db, user, light, focus="a", status=CheckinStatus.SUBMITTED)
    _add_daily(db, user, heavy, focus="a", done="b", mood="great", energy=9, note="c", status=CheckinStatus.SUBMITTED)

    cells = _cells(contribution_graph(db, user))
    assert cells[heavy.isoformat()]["count"] > cells[light.isoformat()]["count"]
    assert cells[heavy.isoformat()]["level"] > cells[light.isoformat()]["level"]


def test_weekly_submission_does_not_light_any_day(db, user):
    """One weekly reflection must never fake a week of daily activity."""
    monday = date.today() - timedelta(days=date.today().weekday())
    db.add(WeeklyCheckin(user_id=user.id, week_start=monday, status=CheckinStatus.SUBMITTED))
    db.commit()

    graph = contribution_graph(db, user)
    cells = _cells(graph)
    for offset in range(7):
        assert cells[(monday + timedelta(days=offset)).isoformat()]["level"] == 0
    assert next(w for w in graph["weeks"] if w["week_start"] == monday.isoformat())["weekly_done"] is True
    assert graph["stats"]["active_days"] == 0
    assert graph["stats"]["weekly_done"] == 1


def test_daily_and_weekly_same_day_still_reports_daily(db, user):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    _add_daily(db, user, today, focus="x", status=CheckinStatus.SUBMITTED)
    db.add(WeeklyCheckin(user_id=user.id, week_start=monday, status=CheckinStatus.SUBMITTED))
    db.commit()

    graph = contribution_graph(db, user)
    cell = _cells(graph)[today.isoformat()]
    assert cell["kind"] == "check-in"
    assert cell["count"] == 2                  # base + focus field, no weekly bonus
    assert cell["level"] == 2
    assert "weekly" not in cell["note"]
    assert next(w for w in graph["weeks"] if w["week_start"] == monday.isoformat())["weekly_done"] is True


def test_streak_counts_consecutive_active_days(db, user):
    today = date.today()
    for back in range(3):
        _add_daily(db, user, today - timedelta(days=back), focus="x", status=CheckinStatus.SUBMITTED)

    stats = contribution_graph(db, user)["stats"]
    assert stats["current_streak"] == 3
    assert stats["best_streak"] == 3
    assert stats["active_days"] == 3


def test_weekly_only_history_leaves_every_streak_at_zero(db, user):
    """A week of weekly reflections is not a streak of daily check-ins."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    for back in range(1, 4):
        db.add(WeeklyCheckin(user_id=user.id, week_start=monday - timedelta(weeks=back), status=CheckinStatus.SUBMITTED))
    db.commit()

    stats = contribution_graph(db, user)["stats"]
    assert stats["current_streak"] == 0
    assert stats["best_streak"] == 0
    assert stats["active_days"] == 0
    assert stats["weekly_done"] == 3


def test_graph_never_returns_days_outside_the_window(db, user):
    graph = contribution_graph(db, user, weeks=4)
    dates = [c["date"] for w in graph["weeks"] for c in w["days"]]
    assert len(dates) == len(set(dates)) == 28
    monday = date.today() - timedelta(days=date.today().weekday())
    assert min(dates) == (monday - timedelta(weeks=3)).isoformat()


def test_endpoint_isolates_users(db, user):
    other = user.__class__(email="other@test.local", password_hash="x", grade=9)
    db.add(other)
    db.commit()
    _add_daily(db, user, date.today(), focus="mine", status=CheckinStatus.SUBMITTED)

    assert contribution_graph(db, other)["stats"]["active_days"] == 0
    assert contribution_graph(db, user)["stats"]["active_days"] == 1


def test_weeks_query_param_is_honoured(client):
    for w in (4, 12, 53):
        body = client.get(f"/api/v1/checkins/graph?weeks={w}").json()
        assert len(body["weeks"]) == w
        assert set(body["stats"]) == {"current_streak", "best_streak", "active_days", "weekly_done"}


def _add_messages(db, user, day, count):
    conv = Conversation(user_id=user.id, title=f"chat {day}")
    db.add(conv)
    db.flush()
    for i in range(count):
        db.add(
            Message(
                conversation_id=conv.id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content="hi",
                created_at=datetime(day.year, day.month, day.day, 10 + (i % 8)),
            )
        )
    db.commit()


def test_chatting_greens_the_day(db, user):
    day = date.today() - timedelta(days=1)
    _add_messages(db, user, day, 4)          # 2 student messages + 2 replies

    cell = _cells(contribution_graph(db, user))[day.isoformat()]
    assert cell["level"] > 0
    assert "chat" in cell["kind"]
    assert "messages to Novi" in cell["note"]


def test_assistant_replies_alone_do_not_green_the_day(db, user):
    """Only the student's own messages count, not Novi's replies."""
    day = date.today() - timedelta(days=1)
    conv = Conversation(user_id=user.id, title="one-sided")
    db.add(conv)
    db.flush()
    for _ in range(3):
        db.add(Message(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="ok",
                       created_at=datetime(day.year, day.month, day.day, 12)))
    db.commit()

    assert _cells(contribution_graph(db, user))[day.isoformat()]["level"] == 0


def test_completed_planner_block_greens_the_day(db, user):
    day = date.today() - timedelta(days=2)
    db.add(ScheduleBlock(user_id=user.id, date=day, title="Algebra", minutes=45, completed=True))
    db.add(ScheduleBlock(user_id=user.id, date=day, title="Reading", minutes=30, completed=False))
    db.commit()

    cell = _cells(contribution_graph(db, user))[day.isoformat()]
    assert cell["level"] > 0
    assert "blocks" in cell["kind"]
    assert "1 block done" in cell["note"]


def test_busier_day_is_darker(db, user):
    quiet = date.today() - timedelta(days=1)
    busy = date.today() - timedelta(days=2)
    _add_messages(db, user, quiet, 2)         # 1 student message
    _add_messages(db, user, busy, 10)         # 5 student messages
    db.add(ScheduleBlock(user_id=user.id, date=busy, title="Algebra", minutes=45, completed=True))

    cells = _cells(contribution_graph(db, user))
    assert cells[busy.isoformat()]["count"] > cells[quiet.isoformat()]["count"]
    assert cells[busy.isoformat()]["level"] > cells[quiet.isoformat()]["level"]


def test_all_three_sources_combine_on_one_day(db, user):
    day = date.today() - timedelta(days=1)
    _add_daily(db, user, day, focus="Algebra", done="5 problems", mood="good", energy=8,
               status=CheckinStatus.SUBMITTED)
    _add_messages(db, user, day, 4)
    db.add(ScheduleBlock(user_id=user.id, date=day, title="Algebra", minutes=45, completed=True))
    db.commit()

    cell = _cells(contribution_graph(db, user))[day.isoformat()]
    assert set(cell["kind"].split("+")) == {"check-in", "chat", "blocks"}
    assert cell["count"] == 8          # 5 check-in fields + 2 messages + 1 block
    assert cell["level"] == 4


def test_other_users_activity_is_not_counted(db, user):
    other = user.__class__(email="quiet@test.local", password_hash="x", grade=9)
    db.add(other)
    db.commit()
    day = date.today() - timedelta(days=1)
    _add_messages(db, other, day, 6)
    db.add(ScheduleBlock(user_id=other.id, date=day, title="Theirs", minutes=30, completed=True))
    db.commit()

    assert _cells(contribution_graph(db, other))[day.isoformat()]["level"] > 0
    assert _cells(contribution_graph(db, user))[day.isoformat()]["level"] == 0


def test_cell_notes_are_human_readable(db, user):
    day = date.today()
    _add_daily(db, user, day, focus="Finish the heatmap", status=CheckinStatus.SUBMITTED)
    cell = _cells(contribution_graph(db, user))[day.isoformat()]
    assert "check-in" in cell["note"]
    assert "Finish the heatmap" in cell["note"]