"""Tests for the daily planner service (agenda, check-in, blocks, auto-plan)."""

from datetime import date, timedelta

import pytest

from app.models.enums import PrioritySkill
from app.models.roadmap import WeeklyPriority
from app.schemas.checkin import CheckinCreate
from app.schemas.planner import DailyCheckinSave, ScheduleBlockCreate
from app.services import checkins as planner


@pytest.fixture()
def priority(db, user):
    p = WeeklyPriority(
        user_id=user.id,
        week_start=planner._week_start(date.today()),
        ordinal=1,
        skill_category=PrioritySkill.BUILD,
        title="Revise data structures",
        minutes=90,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_get_day_has_week_calendar_and_checkin(db, user):
    day = planner.get_day(db, user, date.today())
    assert day["date"] == date.today().isoformat()
    assert len(day["week"]) == 7
    assert len(day["month"]["days"]) == 42
    assert day["month"]["label"]
    assert day["checkin"]["status"] == "draft"
    assert day["stats"]["open"] == 0


def test_daily_checkin_is_upserted_and_submitted(db, user):
    planner.save_daily_checkin(db, user, DailyCheckinSave(focus="Ship the planner"))
    saved = planner.save_daily_checkin(
        db, user, DailyCheckinSave(focus="Ship the planner", mood="good", energy=8)
    )
    assert saved["focus"] == "Ship the planner"
    assert saved["mood"] == "good"
    assert saved["energy"] == 8
    assert saved["status"] == "submitted"
    assert db.query(planner.DailyCheckin).filter_by(user_id=user.id).count() == 1


def test_manual_blocks_crud_and_toggle(db, user):
    block = planner.create_block(
        db, user, ScheduleBlockCreate(date=date.today(), title="Read ch.3", start_time="09:00", end_time="09:45", minutes=45)
    )
    assert block["start_time"] == "09:00"
    assert block["completed"] is False

    toggled = planner.toggle_block(db, user, block["id"])
    assert toggled["completed"] is True

    assert planner.delete_block(db, user, block["id"]) is True
    assert planner.delete_block(db, user, block["id"]) is False


def test_blocks_are_scoped_to_the_selected_day(db, user):
    planner.create_block(db, user, ScheduleBlockCreate(date=date.today(), title="Today"))
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert planner.get_day(db, user, tomorrow)["blocks"] == []


def test_auto_plan_uses_priority_and_is_idempotent(db, user, priority):
    planned = planner.auto_plan(db, user, date.today())
    auto = [b for b in planned["blocks"] if b["source"] == "auto"]
    assert any(b["linked_type"] == "priority" and b["title"] == priority.title for b in auto)

    once = len(planner.list_blocks(db, user, date.today()))
    planner.auto_plan(db, user, date.today())
    assert len(planner.list_blocks(db, user, date.today())) == once


def test_completing_an_auto_block_completes_its_priority(db, user, priority):
    planned = planner.auto_plan(db, user, date.today())
    block = next(b for b in planned["blocks"] if b["linked_type"] == "priority")
    planner.toggle_block(db, user, block["id"])
    db.refresh(priority)
    assert priority.completed is True


def test_weekly_answers_seed_next_week_priorities(db, user):
    planner.save_answers(
        db,
        user,
        CheckinCreate(next_week="Finish unit 4, Mock interview, Read ch.5"),
    )
    next_week = planner._week_start(date.today()) + timedelta(days=7)
    titles = [p["title"] for p in planner.get_day(db, user, next_week)["priorities"]]
    assert titles == ["Finish unit 4", "Mock interview", "Read ch.5"]


def test_daily_checkins_roll_up_into_weekly_summary(db, user):
    planner.save_daily_checkin(
        db, user, DailyCheckinSave(focus="Algebra", done="5 problems", mood="good", energy=7)
    )
    planner.save_daily_checkin(
        db,
        user,
        DailyCheckinSave(
            date=date.today() + timedelta(days=1), focus="Physics", done="Lab notes", mood="ok", energy=5
        ),
    )

    rollup = planner.daily_rollup(db, user, planner._week_start(date.today()))
    assert rollup["days"] == 2
    assert rollup["avg_energy"] == 6.0
    assert set(rollup["wins"]) == {"5 problems", "Lab notes"}
    assert rollup["moods"] == {"good": 1, "ok": 1}

    fallback = planner._fallback_summary(
        {"accomplishments": "Shipped the planner", "learnings": "SQL joins", "next_week": "Practice mocks"},
        rollup,
    )
    assert fallback["wins"] == 3
    assert fallback["milestones"][0] == "Shipped the planner"


def test_contribution_graph_counts_daily_only(db, user):
    """Daily check-ins green the grid; a weekly reflection must not fake 7 days."""
    today = date.today()
    planner.save_daily_checkin(
        db, user, DailyCheckinSave(date=today, focus="Algebra", done="5 problems", mood="good", energy=8)
    )
    planner.save_answers(db, user, CheckinCreate(accomplishments="Shipped the planner"))

    graph = planner.contribution_graph(db, user, weeks=4)
    assert len(graph["weeks"]) == 4
    flat = [day for week in graph["weeks"] for day in week["days"]]
    today_cell = next(d for d in flat if d["date"] == today.isoformat())
    assert today_cell["kind"] == "check-in"
    assert today_cell["count"] == 5           # filled daily fields only
    assert today_cell["level"] == 3

    # the weekly reflection is a separate track, not seven green days
    monday = planner._week_start(today)
    this_week = next(w for w in graph["weeks"] if w["week_start"] == monday.isoformat())
    assert this_week["weekly_done"] is True
    for offset in range(7):
        if offset == today.weekday():
            continue  # today legitimately has its own daily check-in
        later = next(d for d in this_week["days"] if d["date"] == (monday + timedelta(days=offset)).isoformat())
        assert later["level"] == 0, "a weekly reflection must not green days without a daily check-in"
        assert later["kind"] == ""

    prev_week = next(w for w in graph["weeks"] if w["week_start"] == (monday - timedelta(days=7)).isoformat())
    assert prev_week["weekly_done"] is False

    assert graph["stats"]["active_days"] == 1
    assert graph["stats"]["weekly_done"] == 1
