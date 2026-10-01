import asyncio
import json
import re
import time
from typing import Any

from google import genai
from google.genai import types

from app.core.config import settings
from app.llm.base import LLMError, LLMProvider


class GeminiProvider(LLMProvider):
    """Gemini-backed LLM provider with free-tier friendly rate limiting and
    robust JSON extraction."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.client = genai.Client(api_key=self._api_key)
        self.min_delay = settings.GEMINI_SYNC_DELAY
        self.last_call_time = 0.0

    async def _throttle(self) -> None:
        await asyncio.sleep(self.min_delay)

    @staticmethod
    def _retry_delay(exc: Exception) -> float | None:
        """Pull the server's suggested retry delay from error text (RetryInfo)."""
        msg = str(exc)
        m = re.search(r"retry\s*(?:in|after)?\s*(?:[:(]?\s*)?(\d+(?:\.\d+)?)\s*s?", msg, re.I)
        if not m:
            m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s?"', msg)
        if not m:
            return None
        delay = float(m.group(1))
        return min(max(delay, 2.0), 20.0)

    @staticmethod
    def _transient(exc: Exception) -> bool:
        """Retriable failures only. Quota (429/RESOURCE_EXHAUSTED) is NOT retried:
        a daily limit will not flip within seconds, and the long backoffs blow past
        client/proxy timeouts. Those surface to the engine cooldown + template
        fallback immediately."""
        msg = str(exc)
        return any(k in msg for k in ("503", "UNAVAILABLE", "ConnectError", "ReadTimeout", "connection"))

    async def complete(self, prompt: str, system: str | None = None) -> str:
        if not self._api_key:
            raise LLMError("GEMINI_API_KEY is not configured")

        attempts = 3
        for attempt in range(attempts):
            try:
                await self._throttle()
                contents = [system or "", prompt] if system else [prompt]
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents="\n\n".join(c for c in contents if c),
                    ),
                    timeout=settings.GEMINI_TIMEOUT_SECONDS,
                )
                self.last_call_time = time.time()
                text = (response.text or "").strip()
                if not text:
                    raise LLMError("Empty Gemini response")
                return text
            except Exception as exc:  # pylint: disable=broad-except
                if self._transient(exc) and attempt < attempts - 1:
                    delay = self._retry_delay(exc) or (4 if attempt == 0 else 8)
                    print(f"[gemini] retrying in {delay:.1f}s ({attempt + 1}/{attempts}): {str(exc)[:140]}")
                    await asyncio.sleep(delay)
                    continue
                print(f"[gemini] complete error: {exc}")
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    raise LLMError(
                        "I've hit my daily conversation limit. Please try again tomorrow! 🌅"
                    ) from exc
                raise LLMError("Gemini unavailable") from exc
        raise LLMError("Gemini unavailable")

    async def complete_json(self, prompt: str, system: str | None = None) -> Any:
        for attempt in range(3):
            raw = await self.complete(prompt, system=system)
            parsed = self._extract_json(raw)
            if parsed is not None:
                return parsed
        raise LLMError("Failed to parse JSON from Gemini")

    async def complete_grounded(self, prompt: str, system: str | None = None) -> dict:
        """Gemini with built-in Google Search grounding. Returns:
        {"text": str, "sources": [{"title": str, "uri": str, "domain": str}]}."""
        if not self._api_key:
            raise LLMError("GEMINI_API_KEY is not configured")

        for attempt in range(2):
            try:
                await self._throttle()
                contents = [system or "", prompt] if system else [prompt]
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents="\n\n".join(c for c in contents if c),
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())]
                        ),
                    ),
                    timeout=settings.GEMINI_TIMEOUT_SECONDS,
                )
                self.last_call_time = time.time()
                text = (response.text or "").strip()
                if not text:
                    raise LLMError("Empty Gemini response")
                sources: list[dict] = []
                for candidate in response.candidates or []:
                    meta = getattr(candidate, "grounding_metadata", None)
                    if not meta:
                        continue
                    for chunk in meta.grounding_chunks or []:
                        web = getattr(chunk, "web", None)
                        if web and web.uri:
                            sources.append({"title": web.title or "", "uri": web.uri, "domain": web.domain or ""})
                return {"text": text, "sources": sources}
            except Exception as exc:  # pylint: disable=broad-except
                if self._transient(exc) and attempt < 1:
                    delay = self._retry_delay(exc) or (4 if attempt == 0 else 8)
                    print(f"[gemini] grounded retrying in {delay:.1f}s ({attempt + 1}/2): {str(exc)[:140]}")
                    await asyncio.sleep(delay)
                    continue
                print(f"[gemini] grounded error: {exc}")
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    raise LLMError(
                        "I've hit my daily conversation limit. Please try again tomorrow! 🌅"
                    ) from exc
                raise LLMError("Gemini unavailable") from exc
        raise LLMError("Gemini unavailable")

    @staticmethod
    def _extract_json(text: str) -> Any:
        t = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
        if fence:
            t = fence.group(1).strip()
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            pass
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(t[start : end + 1])
            except json.JSONDecodeError:
                pass
        start = t.find("[")
        end = t.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(t[start : end + 1])
            except json.JSONDecodeError:
                pass
        return None
