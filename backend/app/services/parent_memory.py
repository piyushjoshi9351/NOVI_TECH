"""Read-only, parent-safe access to a student's Letta memory.

Design constraints:

* READ-ONLY. Only ``LettaClient.get_memory`` and ``get_archival`` are reachable
  from here -- no send_message, no insert_archival, no update_memory_block. A
  parent must never be able to write into, or be written into, the student's
  memory.
* The agent id comes from ``student.letta_agent_id`` (DB), never from the request
  body, so a parent cannot aim a read at someone else's agent.
* Only the ``human`` core block is returned: the student's own profile line.
  ``persona`` and any other block are filtered out.
* Archival passages are tag-filtered. Letta tags carry the raw conversation
  imports (``chat``, ``student``, ``novistate``), which must never reach a parent.
* Fails soft: any Letta error yields an empty memory view rather than a 500, so
  a memory outage cannot take down a parent's dashboard.
"""

import logging
from datetime import datetime

from app.core.config import settings
from app.llm.letta import LettaClient
from app.models.user import User
from app.schemas.parent import MemoryPassage, MemoryResponse
from app.services.parent_data import student_ref

logger = logging.getLogger("novi.parent_memory")

MAX_PASSAGES = 50

# Only these tags are considered shareable. Everything else is dropped.
ALLOWED_TAGS = frozenset(
    {
        "milestone",
        "profile",
        "strength",
        "interest",
        "skill",
        "goal",
        "achievement",
        "snapshot",
        "preference",
        "sy",
    }
)

# Never shareable, regardless of what Letta returns. Raw chat imports and Novi's
# internal state are the student's private conversation with their mentor.
BLOCKED_TAGS = frozenset({"chat", "student", "novistate", "conversation"})


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _passage_tags(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(t).strip().lower() for t in raw if str(t).strip()]
    if isinstance(raw, str) and raw.strip():
        return [t.strip().lower() for t in raw.split(",") if t.strip()]
    return []


def _is_shareable(tags: list[str]) -> bool:
    if any(tag in BLOCKED_TAGS for tag in tags):
        return False
    return any(tag in ALLOWED_TAGS or tag.startswith("sy") for tag in tags)


def build_memory(
    student: User,
    link,
    client: LettaClient | None = None,
) -> MemoryResponse:
    """Curated, read-only memory view for a parent.

    Always returns a MemoryResponse; degrades to empty with ``available=False``
    when the student has no agent or Letta is unreachable.
    """
    response = MemoryResponse(
        student=student_ref(student),
        scopes=link.scope_names,
        summary="",
        passages=[],
        available=False,
    )

    agent_id = student.letta_agent_id
    if not agent_id:
        return response

    client = client or LettaClient()
    # An injected client (tests, future transports) opts in implicitly; the real
    # Letta client still respects the LETTA_ENABLED kill switch.
    if client.__class__ is LettaClient and not settings.LETTA_ENABLED:
        return response

    # --- core memory: the student's own "human" profile line only
    try:
        core = client.get_memory(agent_id) or {}
        response.summary = _human_block(core)
    except Exception:
        logger.exception("parent memory: core memory read failed for student %s", student.id)

    # --- archival: tag-filtered, newest first, capped
    try:
        raw_passages = client.get_archival(agent_id) or []
        passages = []
        for raw in raw_passages:
            if not isinstance(raw, dict):
                continue
            text = (raw.get("text") or raw.get("content") or "").strip()
            if not text:
                continue
            tags = _passage_tags(raw.get("tags"))
            if not _is_shareable(tags):
                continue
            passages.append(
                MemoryPassage(
                    id=str(raw["id"]) if raw.get("id") is not None else None,
                    text=text,
                    created_at=_parse_dt(raw.get("created_at")),
                    tags=tags,
                )
            )
        passages.sort(key=lambda p: p.created_at or datetime.min, reverse=True)
        response.passages = passages[:MAX_PASSAGES]
        response.available = True
    except Exception:
        logger.exception("parent memory: archival read failed for student %s", student.id)

    return response


def _human_block(core: dict) -> str:
    """Pull the ``human`` block's value, ignoring persona and any other block."""
    blocks = core.get("memory") if isinstance(core, dict) else None
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and str(block.get("label", "")).strip().lower() == "human":
                return (block.get("value") or "").strip()
    return ""


