from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message
from app.models.checkin import WeeklyCheckin
from app.models.enums import (
    CheckinStatus,
    DailyCheckinStatus,
    GoalStatus,
    MessageRole,
    PrioritySkill,
    TaskStatus,
)
from app.models.planner import DailyCheckin, ScheduleBlock
from app.models.roadmap import Goal, RoadmapItem, Task, WeeklyPriority
from app.models.user import User
from app.llm import prompts
from app.schemas.checkin import CheckinCreate
from app.schemas.planner import DailyCheckinSave, ScheduleBlockCreate
from app.services.career_dna import get_dna
from app.services.providers import dna_dict, gemini, memory


def get_current(db: Session, user: User, start: date | None = None) -> WeeklyCheckin | None:
    s = start or _week_start()
    return db.scalar(
        select(WeeklyCheckin).where(WeeklyCheckin.user_id == user.id, WeeklyCheckin.week_start == s)
    )


def get_or_create_current(db: Session, user: User, start: date | None = None) -> WeeklyCheckin:
    checkin = get_current(db, user, start)
    if checkin:
        return checkin
    s = start or _week_start()
    checkin = WeeklyCheckin(user_id=user.id, week_start=s)
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def save_answers(db: Session, user: User, data: CheckinCreate) -> WeeklyCheckin:
    checkin = get_or_create_current(db, user, data.week_start)
    was_draft = checkin.status == CheckinStatus.DRAFT
    checkin.accomplishments = data.accomplishments
    checkin.learnings = data.learnings
    checkin.challenges = data.challenges
    checkin.pride = data.pride
    checkin.next_week = data.next_week
    if checkin.status == CheckinStatus.DRAFT:
        checkin.status = CheckinStatus.SUBMITTED
    db.commit()
    db.refresh(checkin)
    try:
        sync_priorities_from_checkin(db, user, checkin)
    except Exception as exc:
        db.rollback()
        print(f"[checkins] priority sync failed: {exc}")
    for line in _checkin_lines(checkin):
        memory.archive(user, line, ("checkin",))
    if was_draft:
        try:
            from app.services import growth

            growth.record_event(
                db,
                user,
                "checkin",
                f"Week of {checkin.week_start}",
                growth.event_tags(user, db, f"{checkin.accomplishments} {checkin.learnings}"),
            )
        except Exception as exc:
            db.rollback()
            print(f"[checkins] growth event recording failed: {exc}")
    return checkin


async def summarize(db: Session, user: User, checkin_id: int | None = None) -> WeeklyCheckin:
    checkin = checkin_id and db.get(WeeklyCheckin, checkin_id)
    if not checkin or checkin.user_id != user.id:
        checkin = get_or_create_current(db, user)

    answers = {
        "accomplishments": checkin.accomplishments,
        "learnings": checkin.learnings,
        "challenges": checkin.challenges,
        "pride": checkin.pride,
        "next_week": checkin.next_week,
    }
    summary = None
    dna = get_dna(user, db)
    dna_ctx = dna_dict(dna) if dna else {}
    try:
        result = await gemini.complete_json(
            prompts.checkin_summary_prompt(answers, dna_ctx),
            system=prompts.CHECKIN_SUMMARY_SYSTEM,
        )
        if isinstance(result, dict):
            summary = result
    except Exception as exc:
        print(f"[checkins] summary failed: {exc}")

    rollup = daily_rollup(db, user, checkin.week_start)
    if summary is None:
        summary = _fallback_summary(answers, rollup)

    dna_alignment = str(summary.get("dna_alignment") or "").strip()
    if not dna_alignment and dna:
        goal = (dna.goals or [None])[0]
        zone = (dna.career_zones or [None])[0]
        target = goal or zone
        dna_alignment = (
            f"The work you logged this week moves you toward {target}."
            if target else "This week added evidence for the direction you described."
        )

    checkin.ai_summary = {
        "wins": _int(summary.get("wins"), len(checkin.accomplishments.split(",")) if checkin.accomplishments else 1),
        "new_skills": _list(summary.get("new_skills")),
        "milestones": _list(summary.get("milestones")),
        "priorities_next_week": _list(summary.get("priorities_next_week")),
        "dna_alignment": dna_alignment,
        "daily": rollup,
    }
    checkin.status = CheckinStatus.SUMMARIZED
    db.commit()
    db.refresh(checkin)
    for milestone in _list(summary.get("milestones"))[:3]:
        if milestone:
            memory.archive(user, f"User's weekly milestone: {milestone}.", ("checkin", "milestone"))
    return checkin


def list_checkins(db: Session, user: User, limit: int = 12) -> list[WeeklyCheckin]:
    stmt = (
        select(WeeklyCheckin)
        .where(WeeklyCheckin.user_id == user.id)
        .order_by(WeeklyCheckin.week_start.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def _day_activity_points(
    daily: DailyCheckin | None, msgs: int, blocks: int
) -> tuple[int, list[str]]:
    """Points for one day, plus the list of activity kinds that produced them.

    Three things count: a completed daily check-in (scored by fields filled),
    messages sent to Novi, and completed planner blocks. More activity on a day
    scores higher, so the shade darkens with how busy the day actually was.
    """
    points = 0
    kinds: list[str] = []
    if daily:
        filled = _daily_active(daily)
        if filled:
            points += filled
            kinds.append("check-in")
    if msgs:
        points += min(msgs, 4)
        kinds.append("chat")
    if blocks:
        points += min(blocks, 4)
        kinds.append("blocks")
    return points, kinds


def contribution_graph(db: Session, user: User, weeks: int = 53) -> dict:
    """GitHub-style contribution grid.

    A day turns green when the student did something on that exact calendar day:
    completed a daily check-in, sent messages to Novi, or finished planner
    blocks. The shade (0-4) darkens with how much they did, so a chatty or
    busy day reads heavier than a quiet one.

    A weekly reflection deliberately does NOT light up days: it covers a whole
    week, so treating it as seven green days made the grid lie. Weeks carry a
    separate ``weekly_done`` flag that the UI renders as its own track.
    """
    today = date.today()
    monday = _week_start(today)
    start = monday - timedelta(weeks=weeks - 1)

    dailies = list(
        db.scalars(
            select(DailyCheckin).where(
                DailyCheckin.user_id == user.id, DailyCheckin.date >= start
            )
        )
    )
    weeklies = list(
        db.scalars(
            select(WeeklyCheckin).where(
                WeeklyCheckin.user_id == user.id, WeeklyCheckin.week_start >= start
            )
        )
    )

    daily_by_day: dict[date, DailyCheckin] = {c.date: c for c in dailies}
    weekly_by_start: dict[date, WeeklyCheckin] = {c.week_start: c for c in weeklies}

    msgs_by_day: dict[date, int] = _messages_per_day(db, user, start, today)
    blocks_by_day: dict[date, int] = _completed_blocks_per_day(db, user, start, today)

    def _day_score(d: date) -> tuple[int, int, str, str]:
        """Points, kinds and level for one calendar day from all sources."""
        daily = daily_by_day.get(d)
        msgs = msgs_by_day.get(d, 0)
        blocks = blocks_by_day.get(d, 0)
        points, kinds = _day_activity_points(daily, msgs, blocks)
        level = _score_to_level(points)
        kind = "+".join(kinds)
        return level, points, kind, _day_note(d, daily, msgs, blocks, points, kinds)

    grid = []
    for w in range(weeks):
        ws = start + timedelta(weeks=w)
        days = []
        for i in range(7):
            d = ws + timedelta(days=i)
            level, points, kind, note = _day_score(d)
            days.append(
                {
                    "date": _iso(d),
                    "level": level,
                    "count": points,
                    "kind": kind,
                    "note": note,
                }
            )
        weekly = weekly_by_start.get(ws)
        grid.append(
            {
                "week_start": _iso(ws),
                "days": days,
                "weekly_done": bool(weekly and weekly.status != CheckinStatus.DRAFT),
            }
        )

    active_days = 0
    best = 0
    run = 0
    for week in grid:
        for day in week["days"]:
            if day["level"] > 0:
                active_days += 1
                run += 1
                best = max(best, run)
            else:
                run = 0

    current = 0
    cursor = today
    if _day_score(cursor)[0] == 0:
        cursor -= timedelta(days=1)
    while _day_score(cursor)[0] > 0:
        current += 1
        cursor -= timedelta(days=1)
        if cursor < start:
            break

    weekly_done = sum(1 for c in weeklies if c.status != CheckinStatus.DRAFT)

    return {
        "weeks": grid,
        "stats": {
            "current_streak": current,
            "best_streak": best,
            "active_days": active_days,
            "weekly_done": weekly_done,
        },
    }


def _daily_active(c: DailyCheckin) -> int:
    """Score a daily check-in by the fields the student filled in (0-5)."""
    if c.status == DailyCheckinStatus.DRAFT and not any((c.focus, c.done, c.mood, c.energy, c.note)):
        return 0
    score = 1
    if c.focus:
        score += 1
    if c.done:
        score += 1
    if c.mood:
        score += 1
    if c.energy:
        score += 1
    return score


def _score_to_level(points: int) -> int:
    if points <= 0:
        return 0
    if points == 1:
        return 1
    if points <= 3:
        return 2
    if points <= 5:
        return 3
    return 4


def _messages_per_day(db: Session, user: User, start: date, end: date) -> dict[date, int]:
    """Count of student-sent chat messages per calendar day."""
    rows = db.execute(
        select(func.date(Message.created_at), func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == user.id,
            Message.role == MessageRole.USER,
            func.date(Message.created_at) >= start,
            func.date(Message.created_at) <= end,
        )
        .group_by(func.date(Message.created_at))
    )
    out: dict[date, int] = {}
    for raw, count in rows:
        d = _as_date(raw)
        if d:
            out[d] = int(count)
    return out


def _completed_blocks_per_day(db: Session, user: User, start: date, end: date) -> dict[date, int]:
    """Count of planner blocks the student marked done, per calendar day."""
    rows = db.execute(
        select(ScheduleBlock.date, func.count(ScheduleBlock.id)).where(
            ScheduleBlock.user_id == user.id,
            ScheduleBlock.completed.is_(True),
            ScheduleBlock.date >= start,
            ScheduleBlock.date <= end,
        )
        .group_by(ScheduleBlock.date)
    )
    return {d: int(c) for d, c in rows}


def _as_date(raw) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _day_note(
    d: date,
    daily: DailyCheckin | None,
    msgs: int,
    blocks: int,
    points: int,
    kinds: list[str],
) -> str:
    label = d.strftime("%d %b %Y")
    if not kinds:
        return f"{label} · no activity"
    bits: list[str] = []
    if "check-in" in kinds and daily:
        if daily.focus:
            bits.append(f"check-in: {daily.focus[:40]}")
        else:
            bits.append("daily check-in")
    if msgs:
        bits.append(f"{msgs} message{'s' if msgs != 1 else ''} to Novi")
    if blocks:
        bits.append(f"{blocks} block{'s' if blocks != 1 else ''} done")
    return f"{label} · {' · '.join(bits)}"


def _week_start(d: date | None = None) -> date:
    base = d or date.today()
    return base - timedelta(days=base.weekday())


def _checkin_lines(checkin: WeeklyCheckin) -> list[str]:
    lines = []
    if checkin.accomplishments:
        for item in checkin.accomplishments.split(","):
            item = item.strip()
            if item:
                lines.append(f"User's weekly win: {item}.")
    if checkin.learnings:
        for item in checkin.learnings.split(","):
            item = item.strip()
            if item:
                lines.append(f"User learned: {item}.")
    return lines


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _list(value) -> list[str]:
    return [str(v) for v in (value or []) if str(v)]


def _fallback_summary(answers: dict, rollup: dict | None = None) -> dict:
    accomplishments = answers.get("accomplishments", "")
    learnings = answers.get("learnings", "")
    next_week = answers.get("next_week", "")
    daily_wins = list((rollup or {}).get("wins") or [])
    wins = [x.strip() for x in accomplishments.split(",") if x.strip()] + daily_wins
    return {
        "wins": max(1, len(wins)),
        "new_skills": [x.strip() for x in learnings.split(",") if x.strip()][:3],
        "milestones": wins[:3],
        "priorities_next_week": [x.strip() for x in next_week.split(",") if x.strip()][:3],
    }


# --------------------------------------------------------------------------- shared bridge
def _split_items(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.replace("\n", ",").split(",") if x.strip()]


def daily_rollup(db: Session, user: User, start: date) -> dict:
    """Aggregate the week's daily check-ins so they roll up into the weekly summary."""
    end = start + timedelta(days=7)
    rows = list(
        db.scalars(
            select(DailyCheckin)
            .where(DailyCheckin.user_id == user.id, DailyCheckin.date >= start, DailyCheckin.date < end)
            .order_by(DailyCheckin.date.asc())
        )
    )
    energies = [r.energy for r in rows if r.energy]
    moods: dict[str, int] = {}
    for r in rows:
        if r.mood:
            moods[r.mood] = moods.get(r.mood, 0) + 1
    return {
        "days": len(rows),
        "avg_energy": round(sum(energies) / len(energies), 1) if energies else None,
        "moods": moods,
        "wins": [d for r in rows for d in _split_items(r.done)],
        "focuses": [r.focus for r in rows if r.focus],
        "dates": [_iso(r.date) for r in rows],
    }


def sync_priorities_from_checkin(db: Session, user: User, checkin: WeeklyCheckin) -> list[WeeklyPriority]:
    """Turn 'what to do better next week' answers into next week's planner priorities."""
    target = checkin.week_start + timedelta(days=7)
    items = _split_items(checkin.next_week)
    existing = list(
        db.scalars(
            select(WeeklyPriority).where(
                WeeklyPriority.user_id == user.id, WeeklyPriority.week_start == target
            )
        )
    )
    if not items:
        return existing
    for old in existing:
        db.delete(old)
    stored = []
    for idx, title in enumerate(items[:3], start=1):
        wp = WeeklyPriority(
            user_id=user.id,
            week_start=target,
            ordinal=idx,
            skill_category=PrioritySkill.BUILD,
            title=title[:255],
            minutes=90,
        )
        db.add(wp)
        stored.append(wp)
    db.commit()
    for wp in stored:
        db.refresh(wp)
    return stored


# =========================================================================== planner
# The daily planner lives in the same domain as check-ins: daily pulses feed the
# weekly summary, and weekly answers seed next week's planner priorities.
#
#   - ``get_day``   — one consolidated day payload (agenda, candidates, priorities,
#                     backlog, suggestions, week strip + month calendar, stats)
#   - check-in      — lightweight daily reflection (focus/mood/energy)
#   - blocks        — manual schedule blocks (time-bound or open tasks)
#   - ``auto_plan`` — deterministic "build my schedule": roadmap tasks due today,
#                     urgent tasks, the week's top priority and a weak-area focus
#                     are placed into realistic time slots.
#
# Auto-plan is intentionally rule-based (no LLM at request time) so it is instant,
# predictable and free-tier friendly.
# ===========================================================================
import calendar
import uuid

from app.m3.db.models import Goal as M3Goal
from app.m3.db.models import Milestone as M3Milestone
from app.m3.db.models import Roadmap as M3Roadmap
from app.m3.db.models import Student as M3Student
from app.m3.db.models import Task as M3Task

_SLOTS = [("10:00", "11:00"), ("14:00", "15:00"), ("16:00", "17:00"), ("18:00", "19:00")]


# --------------------------------------------------------------------------- date helpers
def parse_date(value: str | date | None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return date.today()


def _iso(d: date) -> str:
    return d.isoformat()


def _fmt_time(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t else None


def _parse_time(value: str | None) -> time | None:
    if not value or not str(value).strip():
        return None
    try:
        return time.fromisoformat(str(value).strip())
    except ValueError:
        return None


def week_dates(d: date) -> list[date]:
    start = _week_start(d)
    return [start + timedelta(days=i) for i in range(7)]


def month_grid(d: date) -> dict:
    """Calendar page for the month containing ``d`` (Monday-first, padded rows)."""
    first = d.replace(day=1)
    start_weekday = first.weekday()
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    today = date.today()
    cells = []
    for offset in range(-start_weekday, 42 - start_weekday):
        cell_date = first + timedelta(days=offset)
        cells.append(
            {
                "iso": _iso(cell_date),
                "day": cell_date.day,
                "in_month": cell_date.month == d.month,
                "is_today": cell_date == today,
                "is_selected": cell_date == d,
            }
        )
    return {
        "label": f"{calendar.month_name[d.month]} {d.year}",
        "month": d.month,
        "year": d.year,
        "days": cells,
    }


# --------------------------------------------------------------------------- source lookups
def _m3_task_for(db: Session, task_id: str) -> M3Task | None:
    try:
        return db.get(M3Task, uuid.UUID(str(task_id)))
    except (ValueError, TypeError):
        return None


def _block_done(db: Session, block: ScheduleBlock) -> bool:
    """Effective completion: respects the linked source item's own state."""
    if block.completed:
        return True
    try:
        if block.linked_type == "m3_task":
            task = _m3_task_for(db, block.linked_id)
            return task is not None and task.status == "completed"
        if block.linked_type == "priority":
            prio = db.get(WeeklyPriority, int(block.linked_id))
            return prio is not None and prio.completed
        if block.linked_type == "roadmap_item":
            item = db.get(RoadmapItem, int(block.linked_id))
            return item is not None and item.completed
        if block.linked_type == "task":
            task = db.get(Task, int(block.linked_id))
            return task is not None and task.status == TaskStatus.DONE
    except (ValueError, TypeError):
        pass
    return block.completed


def _serialize_block(db: Session, block: ScheduleBlock) -> dict:
    return {
        "id": block.id,
        "date": _iso(block.date),
        "title": block.title,
        "kind": block.kind,
        "start_time": _fmt_time(block.start_time),
        "end_time": _fmt_time(block.end_time),
        "minutes": block.minutes,
        "source": block.source,
        "linked_type": block.linked_type,
        "linked_id": block.linked_id,
        "completed": _block_done(db, block),
        "order_index": block.order_index,
        "created_at": block.created_at.isoformat() if block.created_at else None,
    }


def _roadmap_tasks_for_date(db: Session, user: User, d: date) -> list[dict]:
    """Active m3 tasks scheduled on ``d`` for this student, in plan order."""
    stmt = (
        select(M3Task, M3Milestone.title, M3Goal.title)
        .join(M3Milestone, M3Task.milestone_id == M3Milestone.id)
        .join(M3Roadmap, M3Milestone.roadmap_id == M3Roadmap.id)
        .join(M3Goal, M3Roadmap.goal_id == M3Goal.id)
        .join(M3Student, M3Goal.student_id == M3Student.id)
        .where(
            M3Student.user_id == user.id,
            M3Roadmap.status == "active",
            M3Task.target_date == d,
            M3Task.status.in_(["pending", "active"]),
        )
        .order_by(M3Milestone.order_index.asc(), M3Task.order_index.asc())
    )
    return [
        {
            "id": str(task.id),
            "title": task.title,
            "milestone": milestone_title,
            "goal": goal_title,
            "status": task.status,
            "priority": task.priority,
            "target_date": _iso(task.target_date) if task.target_date else None,
        }
        for task, milestone_title, goal_title in db.execute(stmt).all()
    ]


def _legacy_tasks_due(db: Session, user: User, d: date) -> list[dict]:
    stmt = (
        select(Task)
        .where(
            Task.user_id == user.id,
            Task.due_date == d,
            Task.status != TaskStatus.DONE,
        )
        .order_by(Task.created_at.asc())
    )
    return [
        {"id": t.id, "title": t.title, "category": t.category, "due_date": _iso(t.due_date)}
        for t in db.scalars(stmt).all()
    ]


def _current_priorities(db: Session, user: User, d: date) -> list[WeeklyPriority]:
    start = _week_start(d)
    return list(
        db.scalars(
            select(WeeklyPriority)
            .where(WeeklyPriority.user_id == user.id, WeeklyPriority.week_start == start)
            .order_by(WeeklyPriority.ordinal.asc())
        )
    )


def _backlog(db: Session, user: User, d: date) -> list[dict]:
    rows: list[dict] = []
    # Incomplete roadmap items for active goals, most recent goal first.
    items = (
        select(RoadmapItem, Goal.title)
        .join(Goal, RoadmapItem.goal_id == Goal.id)
        .where(
            RoadmapItem.user_id == user.id,
            RoadmapItem.completed.is_(False),
            Goal.status == GoalStatus.ACTIVE,
        )
        .order_by(Goal.created_at.asc(), RoadmapItem.order_index.asc())
        .limit(8)
    )
    for item, goal_title in db.execute(items).all():
        rows.append(
            {"id": item.id, "title": item.title, "source": "roadmap", "meta": f"Goal: {goal_title}"}
        )
    # Open legacy tasks not due today.
    open_tasks = list(
        db.scalars(
            select(Task)
            .where(Task.user_id == user.id, Task.status != TaskStatus.DONE)
            .order_by(Task.created_at.asc())
            .limit(6)
        )
    )
    for task in open_tasks:
        if task.due_date and task.due_date <= d:
            continue
        rows.append(
            {"id": task.id, "title": task.title, "source": "task", "meta": "Open task"}
        )
    # This week's priorities still open.
    for prio in _current_priorities(db, user, d):
        if not prio.completed:
            rows.append(
                {
                    "id": prio.id,
                    "title": prio.title,
                    "source": "priority",
                    "meta": f"Priority · {prio.minutes} min",
                }
            )
    return rows[:8]


def _suggestions(db: Session, user: User, d: date) -> list[dict]:
    """Things Novi suggests working on today (deterministic, evidence-based)."""
    out: list[dict] = []
    try:
        from app.services.readiness import accumulated_readiness

        readiness = accumulated_readiness(db, user)
        if readiness.get("next_move"):
            out.append(
                {
                    "title": readiness["next_move"],
                    "why": f"Your weakest signal is {_weakest_label(readiness)}.",
                    "source": "Coach",
                }
            )
    except Exception as exc:
        print(f"[planner] readiness suggestion failed: {exc}")

    # The next scheduled m3 task (after today) keeps the plan moving.
    upcoming = _next_m3_tasks(db, user, d)
    if upcoming:
        t = upcoming[0]
        out.append(
            {
                "title": t["title"],
                "why": "Next scheduled step on your roadmap.",
                "source": "Roadmap",
            }
        )

    # An incomplete weekly priority is the week's agreed commitment.
    for prio in _current_priorities(db, user, d):
        if not prio.completed and len(out) < 3:
            out.append(
                {
                    "title": prio.title,
                    "why": "The priority you set for this week.",
                    "source": "Priority",
                }
            )
            break
    return out[:3]


def _weakest_label(readiness: dict) -> str:
    try:
        weakest = min(readiness.get("components", []), key=lambda c: c["points"])
        return weakest["label"]
    except ValueError:
        return "a growth area"


def _next_m3_tasks(db: Session, user: User, d: date, limit: int = 3) -> list[dict]:
    stmt = (
        select(M3Task, M3Milestone.title, M3Goal.title)
        .join(M3Milestone, M3Task.milestone_id == M3Milestone.id)
        .join(M3Roadmap, M3Milestone.roadmap_id == M3Roadmap.id)
        .join(M3Goal, M3Roadmap.goal_id == M3Goal.id)
        .join(M3Student, M3Goal.student_id == M3Student.id)
        .where(
            M3Student.user_id == user.id,
            M3Roadmap.status == "active",
            M3Task.target_date > d,
            M3Task.status.in_(["pending", "active"]),
        )
        .order_by(M3Task.target_date.asc(), M3Milestone.order_index.asc(), M3Task.order_index.asc())
        .limit(limit)
    )
    return [
        {
            "id": str(task.id),
            "title": task.title,
            "milestone": milestone_title,
            "goal": goal_title,
            "status": task.status,
            "priority": task.priority,
            "target_date": _iso(task.target_date) if task.target_date else None,
        }
        for task, milestone_title, goal_title in db.execute(stmt).all()
    ]


# --------------------------------------------------------------------------- check-in
def get_daily_checkin(db: Session, user: User, d: date) -> DailyCheckin:
    checkin = db.scalar(
        select(DailyCheckin).where(DailyCheckin.user_id == user.id, DailyCheckin.date == d)
    )
    if checkin is None:
        checkin = DailyCheckin(user_id=user.id, date=d)
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
    return checkin


def _checkin_payload(c: DailyCheckin) -> dict:
    return {
        "id": c.id,
        "date": _iso(c.date),
        "focus": c.focus,
        "done": c.done,
        "mood": c.mood,
        "energy": c.energy,
        "note": c.note,
        "status": c.status.value,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _weekly_payload(c: WeeklyCheckin | None) -> dict | None:
    if not c:
        return None
    return {
        "id": c.id,
        "week_start": _iso(c.week_start),
        "status": c.status.value,
        "next_week": c.next_week,
        "summary": c.ai_summary or None,
    }


def save_daily_checkin(db: Session, user: User, data: DailyCheckinSave) -> dict:
    d = data.date or date.today()
    checkin = get_daily_checkin(db, user, d)
    checkin.focus = (data.focus or "").strip()
    checkin.done = (data.done or "").strip()
    checkin.mood = (data.mood or "").strip()
    checkin.energy = data.energy
    checkin.note = (data.note or "").strip()
    has_content = any((checkin.focus, checkin.done, checkin.mood, checkin.energy, checkin.note))
    if has_content and checkin.status == DailyCheckinStatus.DRAFT:
        checkin.status = DailyCheckinStatus.SUBMITTED
    db.commit()
    db.refresh(checkin)
    if checkin.focus:
        try:
            from app.services.providers import memory

            memory.archive(user, f"Today's focus ({d}): {checkin.focus}.", ("planner", "checkin"))
        except Exception as exc:
            print(f"[planner] memory archive failed: {exc}")
    return _checkin_payload(checkin)


# --------------------------------------------------------------------------- blocks
def list_blocks(db: Session, user: User, d: date) -> list[dict]:
    blocks = list(
        db.scalars(
            select(ScheduleBlock)
            .where(ScheduleBlock.user_id == user.id, ScheduleBlock.date == d)
            .order_by(ScheduleBlock.start_time.asc(), ScheduleBlock.order_index.asc())
        )
    )
    return [_serialize_block(db, b) for b in blocks]


def create_block(db: Session, user: User, data: ScheduleBlockCreate) -> dict:
    block = ScheduleBlock(
        user_id=user.id,
        date=data.date,
        title=data.title.strip() or "New task",
        kind=data.kind or "study",
        start_time=_parse_time(data.start_time),
        end_time=_parse_time(data.end_time),
        minutes=data.minutes or 60,
        source="manual",
        completed=False,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return _serialize_block(db, block)


def delete_block(db: Session, user: User, block_id: int) -> bool:
    block = db.get(ScheduleBlock, block_id)
    if block is None or block.user_id != user.id:
        return False
    db.delete(block)
    db.commit()
    return True


def toggle_block(db: Session, user: User, block_id: int) -> dict | None:
    block = db.get(ScheduleBlock, block_id)
    if block is None or block.user_id != user.id:
        return None
    block.completed = not block.completed
    db.commit()
    db.refresh(block)
    if block.completed:
        _propagate_completion(db, user, block)
    return _serialize_block(db, block)


def _propagate_completion(db: Session, user: User, block: ScheduleBlock) -> None:
    """When an auto block is checked off, complete its source item too."""
    try:
        if block.linked_type == "m3_task":
            from app.m3.services.task_service import TaskService
            from app.services import m3_bridge

            chain = m3_bridge.resolve_task_chain(db, user, uuid.UUID(block.linked_id))
            TaskService(db).complete(
                chain["student_id"], chain["goal_id"], chain["roadmap_id"],
                chain["milestone_id"], chain["task_id"],
            )
            if chain.get("legacy_goal") is not None:
                m3_bridge.reconcile_legacy_items(db, user, chain["legacy_goal"], chain["roadmap"])
        elif block.linked_type == "priority":
            prio = db.get(WeeklyPriority, int(block.linked_id))
            if prio is not None and prio.user_id == user.id:
                prio.completed = True
                db.commit()
        elif block.linked_type == "roadmap_item":
            from app.services import roadmap as roadmap_svc

            item = db.get(RoadmapItem, int(block.linked_id))
            if item is not None and item.user_id == user.id and not item.completed:
                roadmap_svc.toggle_roadmap_item(db, user, item.id)
        elif block.linked_type == "task":
            task = db.get(Task, int(block.linked_id))
            if task is not None and task.user_id == user.id:
                task.status = TaskStatus.DONE
                db.commit()
    except Exception as exc:
        print(f"[planner] source completion propagation failed: {exc}")


# --------------------------------------------------------------------------- auto-plan
def _candidates(db: Session, user: User, d: date) -> list[dict]:
    cands: list[dict] = []
    for t in _roadmap_tasks_for_date(db, user, d)[:2]:
        cands.append(
            {
                "title": t["title"],
                "kind": "study",
                "minutes": 90 if t.get("priority") == "high" else 60,
                "linked_type": "m3_task",
                "linked_id": t["id"],
            }
        )
    for t in _legacy_tasks_due(db, user, d)[:1]:
        cands.append({"title": t["title"], "kind": "task", "minutes": 60, "linked_type": "task", "linked_id": str(t["id"])})
    for prio in _current_priorities(db, user, d):
        if not prio.completed:
            cands.append(
                {"title": prio.title, "kind": "priority", "minutes": prio.minutes or 90,
                 "linked_type": "priority", "linked_id": str(prio.id)}
            )
            break
    rows = _backlog(db, user, d)
    for row in rows:
        if row["source"] == "roadmap":
            cands.append(
                {"title": row["title"], "kind": "study", "minutes": 60,
                 "linked_type": "roadmap_item", "linked_id": str(row["id"])}
            )
            break
    seen = set()
    unique = []
    for c in cands:
        key = c["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def auto_plan(db: Session, user: User, d: date) -> dict:
    """Rebuild the day's auto-generated agenda from today's best candidates."""
    for block in db.scalars(
        select(ScheduleBlock).where(
            ScheduleBlock.user_id == user.id, ScheduleBlock.date == d, ScheduleBlock.source == "auto"
        )
    ):
        db.delete(block)
    db.commit()

    candidates = _candidates(db, user, d)
    for idx, (start, end) in enumerate(_SLOTS):
        if idx >= len(candidates):
            break
        c = candidates[idx]
        block = ScheduleBlock(
            user_id=user.id,
            date=d,
            start_time=_parse_time(start),
            end_time=_parse_time(end),
            title=c["title"][:255],
            kind=c["kind"],
            minutes=c["minutes"],
            source="auto",
            linked_type=c["linked_type"],
            linked_id=c["linked_id"],
            completed=False,
            order_index=idx,
        )
        db.add(block)
    db.commit()
    return get_day(db, user, d)


# --------------------------------------------------------------------------- consolidated day
def get_day(db: Session, user: User, value: str | date | None = None) -> dict:
    d = parse_date(value)
    blocks = list_blocks(db, user, d)
    roadmap_tasks = _roadmap_tasks_for_date(db, user, d)
    scheduled_ids = {b["linked_id"] for b in blocks if b["linked_type"] == "m3_task" and b["linked_id"]}
    candidates = [t for t in roadmap_tasks if t["id"] not in scheduled_ids]
    legacy_due = _legacy_tasks_due(db, user, d)
    priorities = [
        {
            "id": p.id,
            "title": p.title,
            "skill_category": p.skill_category.value,
            "minutes": p.minutes,
            "completed": p.completed,
            "ordinal": p.ordinal,
        }
        for p in _current_priorities(db, user, d)
    ]
    backlog = _backlog(db, user, d)
    suggestions = _suggestions(db, user, d)
    checkin = get_daily_checkin(db, user, d)
    weekly_checkin = db.scalar(
        select(WeeklyCheckin).where(
            WeeklyCheckin.user_id == user.id, WeeklyCheckin.week_start == _week_start(d)
        )
    )

    total_minutes = sum(b["minutes"] for b in blocks if not b["completed"])
    open_count = len([b for b in blocks if not b["completed"]]) + len(candidates) + len(legacy_due)

    return {
        "date": _iso(d),
        "week": [
            {
                "date": _iso(dd),
                "weekday": dd.strftime("%a").upper(),
                "day": dd.day,
                "is_today": dd == date.today(),
                "is_selected": dd == d,
            }
            for dd in week_dates(d)
        ],
        "month": month_grid(d),
        "checkin": _checkin_payload(checkin),
        "weekly_checkin": _weekly_payload(weekly_checkin),
        "blocks": blocks,
        "roadmap_tasks": candidates,
        "legacy_tasks": legacy_due,
        "priorities": priorities,
        "backlog": backlog,
        "suggestions": suggestions,
        "classes": [],
        "exams": [],
        "stats": {"open": open_count, "hours": round(total_minutes / 60 * 10) / 10},
    }