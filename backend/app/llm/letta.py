import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import httpx

from app.core.config import settings


def _sanitize_name(name: str) -> str:
    """Keep only characters Letta allows in an agent name."""
    cleaned = re.sub(r"[^A-Za-z0-9 _'-]", "", name or "")
    return cleaned.strip()[:80]


# --------------------------------------------------------------------------- 4-year memory helpers
def school_year(dt: datetime | None = None) -> str:
    """Academic year label e.g. '2026-27' (a year starts on Sept 1)."""
    dt = dt or datetime.now()
    start = dt.year if dt.month >= 9 else dt.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def sy_tag(dt: datetime | None = None) -> str:
    """Tag-safe school-year marker e.g. 'sy202627'."""
    return "sy" + school_year(dt).replace("-", "")


def grade_tag(grade: int | None) -> str:
    return f"grade{grade}" if grade else "grade"


def _fmt(label: str, values: Iterable, fallback: str = "Unknown") -> str:
    vals = [str(v).strip() for v in (values or []) if str(v).strip()]
    return f"{label}: {', '.join(vals) if vals else fallback}."


def build_human_line(
    name: str,
    grade: int | None,
    school: str | None = None,
    interests: Iterable | None = None,
    skills: Iterable | None = None,
    goal: str | None = None,
) -> str:
    """The 'human' core-memory block: the student's live one-line profile."""
    return " ".join(
        [
            f"Name: {name}.",
            f"Grade: {grade or 'unknown'}.",
            _fmt("School", [school] if school else []),
            _fmt("Interests", interests or []),
            _fmt("Skills", skills or []),
            _fmt("Career Goal", [goal] if goal else []),
        ]
    )


def build_milestone(name: str, grade: int | None, school: str | None = None) -> str:
    """One durable fact per academic year marking grade/school progression."""
    sy = school_year()
    bits = [f"SY {sy}: {name} is in Grade {grade or 'unknown'}."]
    if school:
        bits.append(f"School: {school}.")
    return " ".join(bits)


def build_snapshot(
    interests: Iterable | None = None,
    skills: Iterable | None = None,
    goals: Iterable | None = None,
) -> str:
    """Per-year snapshot of the student's evolving profile (interests/skills/goals)."""
    parts = []
    for label, vals in (
        ("Interests", interests or []),
        ("Skills", skills or []),
        ("Career goals", goals or []),
    ):
        line = _fmt(label, vals)
        if line != f"{label}: Unknown.":
            parts.append(line)
    if not parts:
        return ""
    return "SY " + school_year() + " profile. " + " ".join(parts)


class LettaClient:
    """Thin HTTP client for the Letta (MemGPT) memory server.

    All methods raise on failure so callers can fall back gracefully.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.LETTA_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.LETTA_API_KEY

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def is_reachable(self, timeout: float = 3.0) -> bool:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.base_url}/v1/agents/", headers=self._headers(), params={"limit": 1})
                response.raise_for_status()
            return True
        except Exception:  # network / DNS / refused
            return False

    def agent_exists(self, agent_id: str) -> bool:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{self.base_url}/v1/agents/{agent_id}", headers=self._headers())
            if response.status_code == 404:
                return False
            response.raise_for_status()
            return True

    def create_agent(
        self,
        user_id: int,
        name: str,
        grade: int | None,
        school: str | None = None,
        interests: Iterable | None = None,
        skills: Iterable | None = None,
        goal: str | None = None,
    ) -> str:
        safe_name = _sanitize_name(name) or f"student-{user_id}"
        payload = {
            "name": f"Novi-{safe_name}",
            "model": settings.LETTA_MODEL,
            "embedding": settings.LETTA_EMBEDDING,
            "description": f"AI mentor for {safe_name}, Grade {grade}",
            "include_base_tools": False,
            "tools": ["memory", "conversation_search", "archival_memory_insert", "archival_memory_search"],
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.base_url}/v1/agents/", json=payload, headers=self._headers())
            resp.raise_for_status()
            agent_id = resp.json().get("id")

            persona = {
                "label": "persona",
                "description": "My identity as Novi",
                "value": (
                    "You are Novi, an AI mentor for student success — a friendly, "
                    "encouraging and honest guide who helps students discover their future. "
                    "Remember important details about the student over time using the memory tools "
                    "(core memory for the current profile, archival memory for durable multi-year facts)."
                ),
            }
            with httpx.Client(timeout=10.0) as c:
                p = c.post(f"{self.base_url}/v1/_internal_blocks/", json=persona, headers=self._headers())
                if p.status_code == 200:
                    block_id = p.json().get("id")
                    c.patch(
                        f"{self.base_url}/v1/agents/{agent_id}/core-memory/blocks/attach/{block_id}",
                        headers=self._headers(),
                        timeout=10.0,
                    )

            human = {
                "label": "human",
                "description": "Information about the student",
                "value": build_human_line(safe_name, grade, school, interests, skills, goal),
            }
            with httpx.Client(timeout=10.0) as c:
                h = c.post(f"{self.base_url}/v1/_internal_blocks/", json=human, headers=self._headers())
                if h.status_code == 200:
                    block_id = h.json().get("id")
                    c.patch(
                        f"{self.base_url}/v1/agents/{agent_id}/core-memory/blocks/attach/{block_id}",
                        headers=self._headers(),
                        timeout=10.0,
                    )
            return agent_id

    def _is_tool_call(self, s: str) -> bool:
        """Heuristic: llama sometimes hallucinates tool calls as plain-text JSON."""
        t = (s or "").strip()
        return t.startswith("{") and '"name"' in t[:120] and "parameters" in t[:250]

    def _send(self, agent_id: str, message: str) -> list[dict]:
        payload = {"messages": [{"role": "user", "content": message}]}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/agents/{agent_id}/messages", json=payload, headers=self._headers()
            )
            resp.raise_for_status()
            return resp.json().get("messages", [])

    @staticmethod
    def _extract_reply(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("message_type") == "assistant_message" and msg.get("content"):
                return msg["content"]
        return ""

    def send_message(self, agent_id: str, message: str) -> str:
        messages = self._send(agent_id, message)
        reply = self._extract_reply(messages)
        if reply and not self._is_tool_call(reply):
            return reply
        # Nudge the model to produce actual text instead of hallucinating a tool call
        followup = "Now respond in plain text as Novi (do NOT call tools). Give your best advice to the student."
        try:
            messages2 = self._send(agent_id, followup)
            reply2 = self._extract_reply(messages2)
            if reply2 and not self._is_tool_call(reply2):
                return reply2
        except Exception:
            pass
        return reply

    def get_memory(self, agent_id: str) -> dict:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{self.base_url}/v1/agents/{agent_id}/core-memory", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def update_memory_block(self, agent_id: str, label: str, value: str) -> bool:
        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(
                f"{self.base_url}/v1/agents/{agent_id}/core-memory/blocks/{label}",
                json={"value": value},
                headers=self._headers(),
            )
            return resp.status_code == 200

    def search_archival(self, agent_id: str, query: str) -> list:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{self.base_url}/v1/agents/{agent_id}/archival-memory/search",
                params={"query": query},
                headers=self._headers(),
            )
            resp.raise_for_status()
            # The search endpoint labels the passage body "content", while the
            # list/create endpoints label it "text". Normalize to "text" so
            # callers (recall_context, timeline) don't silently read "".
            results = resp.json().get("results", [])
            for r in results:
                if isinstance(r, dict) and "text" not in r and r.get("content") is not None:
                    r["text"] = r["content"]
            return results

    def get_archival(self, agent_id: str) -> list:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{self.base_url}/v1/agents/{agent_id}/archival-memory", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def delete_archival(self, agent_id: str, passage_id: str) -> bool:
        with httpx.Client(timeout=15.0) as client:
            resp = client.delete(
                f"{self.base_url}/v1/agents/{agent_id}/archival-memory/{passage_id}",
                headers=self._headers(),
            )
            return resp.status_code in (200, 204, 404)

    # ------------------------------------------------------------------ dedup
    @staticmethod
    def _normalize(text: str) -> str:
        t = text.lower()
        for token in (
            "user's name is", "user is a", "user is currently in", "user is in",
            "user loves to", "user loves", "user lives in", "user wants to",
            "user joined", "user aspires to", "user enjoys", "user studies",
        ):
            t = t.replace(token, " ")
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        words = []
        for w in t.split():
            if len(w) > 4 and w.endswith("ing"):
                w = w[:-3]
            elif len(w) > 3 and w.endswith("ies"):
                w = w[:-3] + "y"
            elif len(w) > 3 and w.endswith("es"):
                w = w[:-2]
            elif len(w) > 3 and w.endswith("s"):
                w = w[:-1]
            words.append(w)
        return " ".join(words)

    @classmethod
    def _is_near_duplicate(cls, a: str, b: str) -> bool:
        na = cls._normalize(a)
        nb = cls._normalize(b)
        if not na or not nb:
            return False
        if na == nb or na in nb or nb in na:
            return True
        words_a = set(na.split())
        words_b = set(nb.split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
        return overlap >= 0.8

    # ------------------------------------------------------------------ semantic dedup
    # Conservative auxiliary check: only collapses passages that are almost certainly
    # the SAME fact reworded (embedding cosine >= 0.92 with nomic-embed-text).
    # Never throws: any embedding/network failure returns False and we fall back to
    # the word-overlap check above, so archiving is never blocked or slowed hard.

    _EMBED_TIMEOUT = 8.0
    _SEMANTIC_THRESHOLD = 0.92

    @staticmethod
    def _ollama_embeddings_url() -> str:
        """Ollama /api/embeddings endpoint (base without the /v1 suffix)."""
        raw = (settings.OLLAMA_BASE_URL or "http://localhost:11434/v1").rstrip("/")
        base = raw.removesuffix("/v1")
        return f"{base}/api/embeddings"

    @staticmethod
    def _embed(text: str) -> Optional[List[float]]:
        """768-dim nomic-embed-text vector via Ollama. None on ANY failure (never raises)."""
        text = (text or "").strip()
        if not text:
            return None
        try:
            with httpx.Client(timeout=LettaClient._EMBED_TIMEOUT) as client:
                headers = {}
                if settings.OLLAMA_API_KEY:
                    headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

                resp = client.post(
                    LettaClient._ollama_embeddings_url(),
                    headers=headers,
                    json={"model": "nomic-embed-text", "prompt": text[:1200]},
                )
                if resp.status_code != 200:
                    return None
                vec = (resp.json() or {}).get("embedding")
                return vec if isinstance(vec, list) and vec else None
        except Exception:
            return None

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if not na or not nb:
            return 0.0
        return dot / (na * nb)

    @classmethod
    def _semantic_is_near_identical(cls, candidate: str, existing: str) -> bool:
        """True only if the two are almost certainly the same fact reworded. Never throws."""
        try:
            va = cls._embed(candidate)
            vb = cls._embed(existing)
            if not va or not vb:
                return False
            return cls._cosine(va, vb) >= cls._SEMANTIC_THRESHOLD
        except Exception:
            return False

    def insert_archival(
        self, agent_id: str, content: str, tags: Optional[List[str]] = None, dedupe: bool = True
    ) -> bool:
        if not content or not content.strip():
            return False
        if dedupe:
            try:
                existing = self.get_archival(agent_id)
                for passage in existing:
                    base = (passage.get("text") or passage.get("content") or "").strip()
                    if base and self._is_near_duplicate(content, base):
                        return False
                    # semantic second pass (never-throws, conservative): collapses only
                    # near-identical SAME-fact rewordings that word-overlap misses, so the
                    # passage set stays deduped (fast) across years without blocking saves.
                    if base and self._semantic_is_near_identical(content, base):
                        print(f"[letta] semantic dedup: collapsed '{content[:80]}…'")
                        return False
            except Exception as exc:  # proceed anyway
                print(f"[letta] dedup check failed, proceeding: {exc}")
        payload: Dict[str, object] = {"text": content}
        if tags:
            payload["tags"] = tags
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/v1/agents/{agent_id}/archival-memory",
                json=payload,
                headers=self._headers(),
            )
            return resp.status_code == 200
