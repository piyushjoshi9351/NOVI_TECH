"""Memory orchestration: Letta when reachable, graceful Gemini-only fallback.

Chat flow:
  1. If a Letta agent exists and the server is reachable, use it (with recalled
     archival context injected) AND keep Letta's memory fresh.
  2. Otherwise fall back to Gemini directly — behaviour is identical to the user.
"""

from collections import defaultdict
import asyncio
import time
from typing import Iterable, Optional

from app.core.config import settings
from app.llm.engine import NoviEngine
from app.llm.letta import (
    LettaClient,
    build_human_line,
    build_milestone,
    build_snapshot,
    grade_tag,
    sy_tag,
)
from app.llm.prompts import FACT_EXTRACTION_SYSTEM, fact_extraction_prompt, profile_update_prompt


class NoviMemory:
    def __init__(self, letta: Optional[LettaClient] = None, gemini: Optional[NoviEngine] = None):
        self.letta = letta or LettaClient()
        self.gemini = gemini or NoviEngine()
        self._reachable: Optional[bool] = None
        self._last_check = 0.0
        self._ttl = 30.0  # re-check reachability every 30s

    # ------------------------------------------------------------------ state
    def is_reachable(self, force: bool = False) -> bool:
        now = time.time()
        if force or self._reachable is None or (now - self._last_check) > self._ttl:
            self._reachable = settings.LETTA_ENABLED and self.letta.is_reachable()
            self._last_check = now
        return bool(self._reachable)

    def source(self) -> str:
        return "letta" if self.is_reachable() else "gemini"

    # ------------------------------------------------------------------ agent
    def ensure_agent(
        self,
        user_id: int,
        name: str,
        grade: int | None,
        existing: str | None,
        school: str | None = None,
        interests: Iterable | None = None,
        skills: Iterable | None = None,
        goal: str | None = None,
    ) -> Optional[str]:
        """Return the agent id for a user, creating it if needed and Letta is up."""
        if not self.is_reachable():
            return None
        if existing:
            return existing
        try:
            agent_id = self.letta.create_agent(
                user_id=user_id,
                name=name,
                grade=grade,
                school=school,
                interests=interests,
                skills=skills,
                goal=goal,
            )
            # Immediately file the grade/school milestone so the timeline is never empty.
            try:
                self.seed_profile(agent_id, name, grade, school=school)
            except Exception as exc:
                print(f"[memory] seed after create failed: {exc}")
            return agent_id
        except Exception as exc:
            print(f"[memory] create_agent failed: {exc}")
            self._reachable = False
            return None

    def seed_profile(
        self,
        agent_id: str,
        name: str,
        grade: int | None,
        school: str | None = None,
        interests: Iterable | None = None,
        skills: Iterable | None = None,
        goal: str | None = None,
    ) -> bool:
        """Keep the 4-year memory rich for this student.

        Writes/refreshes the live 'human' block AND files one milestone fact (grade/school
        progression per school year) plus one profile snapshot (interests/skills/goals) into
        the durable archival memory. Dedup makes all of this idempotent within a school year,
        so as the student advances grades the timeline accumulates year-by-year.
        """
        if not self.is_reachable():
            return False
        updated = False

        line = build_human_line(name, grade, school, interests, skills, goal)
        try:
            if line and line != self.current_profile(agent_id):
                if self.letta.update_memory_block(agent_id, "human", line):
                    updated = True
        except Exception as exc:
            print(f"[memory] seed human block failed: {exc}")

        # One milestone + one profile snapshot per school year+grade. Identified by tags so
        # they are never fuzzy-deduped against older, simpler facts (e.g. "User is in Grade 11").
        mtags = ["milestone", sy_tag(), grade_tag(grade)]
        ptags = ["profile", sy_tag(), grade_tag(grade)]
        try:
            existing = self.letta.get_archival(agent_id)
        except Exception as exc:
            print(f"[memory] seed read failed: {exc}")
            existing = []

        if not any(all(t in (p.get("tags") or []) for t in mtags) for p in existing):
            try:
                if self.letta.insert_archival(
                    agent_id, build_milestone(name, grade, school), tags=mtags, dedupe=False
                ):
                    updated = True
            except Exception as exc:
                print(f"[memory] seed milestone failed: {exc}")

        snapshot = build_snapshot(interests, skills, [goal] if goal else None)
        if snapshot and not any(all(t in (p.get("tags") or []) for t in ptags) for p in existing):
            try:
                if self.letta.insert_archival(
                    agent_id, snapshot, tags=ptags, dedupe=False
                ):
                    updated = True
            except Exception as exc:
                print(f"[memory] seed snapshot failed: {exc}")

        return updated

    # ------------------------------------------------------------------ chat
    def recall_context(self, agent_id: str, message: str) -> str:
        """Inject relevant long-term archival memory into a message context block.

        Searches twice — on the message itself and on profile keywords — so the agent gets both
        directly relevant facts and the student's moving profile for a better, more personal reply.
        """
        try:
            seen, facts = set(), []

            def add(text: str) -> None:
                t = (text or "").strip()
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    facts.append(t)

            results = self.letta.search_archival(agent_id, message)
            for r in results[:6]:
                add(r.get("text"))
            extra = self.letta.search_archival(
                agent_id, "interests goals skills progress milestones achievements"
            )
            for r in extra[:6]:
                add(r.get("text"))
            if not facts and not self.state_text(agent_id):
                return ""

            parts = []
            state = self.state_text(agent_id)
            if state:
                parts.append(state)
            profile = self.current_profile(agent_id)
            if profile:
                parts.append(f"Current profile: {profile}")
            if facts:
                parts.append("\n".join(f"- {f}" for f in facts[:10]))
            return (
                "Below is long-term memory about this student. Use it to personalize your response.\n"
                "=== MEMORY ===\n"
                f"{chr(10).join(parts)}\n"
                "=== END MEMORY ===\n\n"
            )
        except Exception as exc:
            print(f"[memory] recall failed: {exc}")
            return ""

    def chat(self, agent_id: str, message: str, user=None) -> str:
        """Send via Letta. Raises if Letta can't produce an answer.
        
        Automatically archives the user's message so that memories are
        persisted across sessions — even if no feature explicitly calls
        ``memory.archive()``."""
        context = self.recall_context(agent_id, message)
        payload = f"{context}Student says: {message}" if context else message
        response = self.letta.send_message(agent_id, payload)
        # --- auto‑archive the user's message so it survives a restart ---
        if user is None:
            # Minimal user object; archive() will auto‑create an agent
            # the first time and then reuse the same agent_id thereafter.
            class _User:
                id = 0
                full_name = "User"
                grade = None
                school = None
            user = _User()
        self.archive(user, message, tags=["chat"])
        return response

    def timeline(self, agent_id: str) -> dict:
        """Structured student memory for easy retrieval, grouped by school year.

        Returns {"core_profile": ..., "years": [{school_year, entries: [{grade, milestone, profile, text}]}], "total_facts": n}
        """
        core_profile = self.current_profile(agent_id)
        groups: dict[str, list] = defaultdict(list)
        total = 0
        try:
            arch = self.letta.get_archival(agent_id)
            passages = arch if isinstance(arch, list) else arch.get("passages", [])
            total = len(passages)
            for p in passages:
                text = (p.get("text") or "").strip()
                if not text:
                    continue
                tags = p.get("tags") or []
                label = next((t for t in tags if t.startswith("sy")), None) or "sy-unsorted"
                groups[label].append(
                    {
                        "grade": next((t for t in tags if t.startswith("grade")), None),
                        "milestone": "milestone" in tags,
                        "profile": "profile" in tags,
                        "text": text,
                    }
                )
        except Exception as exc:
            print(f"[memory] timeline failed: {exc}")

        # newest school year first
        years = [{"school_year": label, "entries": groups[label]} for label in sorted(groups, reverse=True)]
        return {"core_profile": core_profile, "years": years, "total_facts": total}

    def current_profile(self, agent_id: str) -> str:
        try:
            blocks = self.letta.get_memory(agent_id).get("blocks", [])
            human = next((b for b in blocks if b.get("label") == "human"), None)
            return (human or {}).get("value", "")
        except Exception:
            return ""

    # ------------------------------------------------------------------ feature integration
    _STATE_TAG = "novistate"

    def set_state(self, agent_id: str, text: str, grade: int | None = None) -> bool:
        """Replace the student's CURRENT app-state passage with a fresh snapshot.

        Exactly one state passage exists per student (tagged 'novistate'), so
        chat always recalls the latest roadmap / passport / task situation rather
        than an ever-growing pile of stale facts.
        """
        if not text or not text.strip() or not self.is_reachable():
            return False
        try:
            existing = self.letta.get_archival(agent_id)
            passages = existing if isinstance(existing, list) else existing.get("passages", [])
            for p in passages:
                if self._STATE_TAG in (p.get("tags") or []):
                    try:
                        self.letta.delete_archival(agent_id, str(p["id"]))
                    except Exception as exc:
                        print(f"[memory] state delete failed: {exc}")
            tags = [self._STATE_TAG, grade_tag(grade) if grade else "grade"]
            return self.letta.insert_archival(agent_id, text.strip(), tags=tags, dedupe=False)
        except Exception as exc:
            print(f"[memory] set_state failed: {exc}")
            return False

    def state_text(self, agent_id: str) -> str:
        """Return the freshest state passage (empty string when none / unreachable)."""
        try:
            existing = self.letta.get_archival(agent_id)
            passages = existing if isinstance(existing, list) else existing.get("passages", [])
            for p in reversed(passages):
                if self._STATE_TAG in (p.get("tags") or []):
                    t = (p.get("text") or "").strip()
                    if t:
                        return t
        except Exception as exc:
            print(f"[memory] state read failed: {exc}")
        return ""

    def archive(self, user, fact: str, tags: Iterable[str] = ()) -> bool:
        """Archive a durable fact from ANY feature (DNA, passport, check-ins, roadmap, ...)
        into the student's Letta archival memory, tagged with school year + grade.

        If the user has no Letta agent yet, one is created on the fly and its ID
        is saved to the user's DB record so it stays the same for every future interaction."""
        agent = getattr(user, "letta_agent_id", None)
        if not agent:
            # auto‑create an agent for this user using name/grade/school from the user model
            name = getattr(user, "full_name", "") or f"User {getattr(user, 'id', '')}"
            grade = getattr(user, "grade", None)
            school = getattr(user, "school", None)
            new_agent = self.ensure_agent(
                user_id=getattr(user, "id", 0),
                name=name,
                grade=grade,
                existing=None,
                school=school,
            )
            if not new_agent:
                return False
            agent = new_agent
            # *** Persist the new agent ID so future calls reuse the same agent ***
            from app.core.database import get_db
            from sqlalchemy import update as sq_update
            from app.models.user import User as UserModel
            try:
                db_gen = get_db()
                db = next(db_gen)
                db.execute(
                    sq_update(UserModel).where(UserModel.id == getattr(user, "id", 0))
                    .values(letta_agent_id=agent)
                )
                db.commit()
                db.commit()
            except Exception as exc:
                print(f"[memory] failed to save letta_agent_id to DB: {exc}")
        if not self.is_reachable() or not fact or not fact.strip():
            return False
        full_tags = list(tags) + [sy_tag(), grade_tag(getattr(user, "grade", None))]
        try:
            return self.letta.insert_archival(agent, fact.strip(), tags=full_tags)
        except Exception as exc:
            print(f"[memory] archive failed: {exc}")
            return False

    def sync_profile(self, user, name: str, grade: int | None, school=None,
                     interests: Iterable | None = None, skills: Iterable | None = None,
                     goal: str | None = None) -> bool:
        """Refresh the live human block + per-year milestone/snapshot after a DNA change."""
        agent = getattr(user, "letta_agent_id", None)
        if not agent or not self.is_reachable():
            return False
        try:
            return self.seed_profile(
                agent, name, grade, school=school, interests=interests or [],
                skills=skills or [], goal=goal,
            )
        except Exception as exc:
            print(f"[memory] sync_profile failed: {exc}")
            return False

    # ------------------------------------------------------------------ writes
    async def update_profile_from_chat(
        self, agent_id: str, chat_history: list[dict], user_context: dict
    ) -> bool:
        try:
            current = self.current_profile(agent_id)
            prompt = profile_update_prompt(chat_history, current)
            new_value = (await self.gemini.complete(prompt, system="")).strip()
            if not new_value or new_value == current:
                return False
            return await asyncio.to_thread(self.letta.update_memory_block, agent_id, "human", new_value)
        except Exception as exc:
            print(f"[memory] profile update failed: {exc}")
            return False

    async def store_facts(self, agent_id: str, chat_history: list[dict], grade: int | None) -> int:
        """Extract durable facts from recent chat and archive them (deduped + grade-tagged)."""
        if not self.is_reachable():
            return 0
        try:
            extracted = await self.gemini.complete_json(
                fact_extraction_prompt(chat_history), system=FACT_EXTRACTION_SYSTEM
            )
            facts = []
            if isinstance(extracted, dict):
                facts = extracted.get("facts") or extracted.get("fact") or []
            elif isinstance(extracted, list):
                facts = extracted
            if not isinstance(facts, list):
                return 0

            tag = f"grade{grade}" if grade else "grade"
            inserted = 0
            for fact in facts[:5]:
                if not isinstance(fact, str) or not fact.strip():
                    continue
                if await asyncio.to_thread(self.letta.insert_archival, agent_id, fact.strip(), tags=["student", sy_tag(), tag]):
                    inserted += 1
            return inserted
        except Exception as exc:
            print(f"[memory] store_facts failed: {exc}")
            return 0
