"""Check that a fresh Letta agent can store core and archival memory.

Run from backend with ``python scripts/smoke_letta.py``. The temporary agent is
deleted in a finally block; no student data is used.
"""

import uuid
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.services.providers import memory


def main() -> None:
    base = settings.LETTA_BASE_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.LETTA_API_KEY}"} if settings.LETTA_API_KEY else {}
    agent_id = None
    with httpx.Client(timeout=45, headers=headers) as client:
        try:
            agent_id = memory.ensure_agent(
                user_id=int(uuid.uuid4().int % 10_000_000),
                name="Memory Smoke",
                grade=10,
                existing=None,
            )
            assert agent_id, "Letta did not create an agent"
            core = client.get(f"{base}/v1/agents/{agent_id}/core-memory")
            core.raise_for_status()
            labels = {block["label"] for block in core.json().get("blocks", [])}
            assert {"persona", "human"}.issubset(labels), labels
            archived = client.post(
                f"{base}/v1/agents/{agent_id}/archival-memory",
                json={"text": "Test student completed a science project."},
            )
            archived.raise_for_status()
            passages = client.get(f"{base}/v1/agents/{agent_id}/archival-memory")
            passages.raise_for_status()
            assert any("science project" in p.get("text", "") for p in passages.json())
            print("Letta agent, core memory, and archival memory: OK")
        finally:
            if agent_id:
                client.delete(f"{base}/v1/agents/{agent_id}").raise_for_status()


if __name__ == "__main__":
    main()
