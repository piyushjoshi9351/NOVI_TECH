"""Resilient LLM engine: Gemini first, local Ollama fallback.

Every AI feature in NOVI (DNA, matches, readiness, roadmaps, check-ins, memory
extraction) flows through this so that a exhausted/absent Gemini quota never
breaks the product — the local Ollama model keeps everything working offline.
"""

import json
import time
from typing import Any

import httpx

from app.core.config import settings
from app.llm.base import LLMError
from app.llm.gemini import GeminiProvider


class OllamaProvider:
    """Local (or LAN) Ollama provider, OpenAI-compatible."""

def __init__(self, base_url: str | None = None, model: str | None = None):
    self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    self.model = model or settings.OLLAMA_MODEL
    self.api_key = settings.OLLAMA_API_KEY

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                    json={"model": self.model, "messages": messages, "temperature": 0.4},
                )
                resp.raise_for_status()
                text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
                if not text:
                    raise LLMError("Empty Ollama response")
                return text
        except Exception as exc:
            raise LLMError(f"Ollama unavailable: {exc}") from exc

    async def complete_json(self, prompt: str, system: str | None = None) -> Any:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            async with httpx.AsyncClient(timeout=240.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMError(f"Ollama JSON unavailable: {exc}") from exc

        parsed = None
        if isinstance(content, str):
            parsed = GeminiProvider._extract_json(content)
        if parsed is not None:
            return parsed
        raise LLMError("Failed to parse JSON from Ollama")

    async def complete_grounded(self, prompt: str, system: str | None = None) -> dict:
        text = await self.complete(prompt, system=system)
        return {"text": text, "sources": []}


class NoviEngine:
    """Primary=Gemini, fallback=Ollama. Exposes complete / complete_json.

    Once Gemini reports quota exhaustion it is skipped for a cooldown window so the
    app stays snappy instead of paying the Gemini timeout on every single call.
    """

    def __init__(self, primary=None, fallback=None):
        self.primary = primary or GeminiProvider()
        self.fallback = fallback or OllamaProvider()
        self._exhausted_until = 0.0

    def _use_primary(self) -> bool:
        return time.time() >= self._exhausted_until

    async def complete(self, prompt: str, system: str | None = None) -> str:
        if not self._use_primary():
            try:
                return await self.fallback.complete(prompt, system=system)
            except LLMError:
                return await self.primary.complete(prompt, system=system)
        try:
            return await self.primary.complete(prompt, system=system)
        except LLMError as exc:
            self._mark_down(exc)
            return await self.fallback.complete(prompt, system=system)

    async def complete_json(self, prompt: str, system: str | None = None) -> Any:
        if not self._use_primary():
            try:
                return await self.fallback.complete_json(prompt, system=system)
            except LLMError:
                return await self.primary.complete_json(prompt, system=system)
        try:
            return await self.primary.complete_json(prompt, system=system)
        except LLMError as exc:
            self._mark_down(exc)
            return await self.fallback.complete_json(prompt, system=system)

    async def complete_grounded(self, prompt: str, system: str | None = None) -> dict:
        """Web-search grounded completion (Gemini Google Search). Falls back to
        plain completion (no sources) when grounding is unavailable."""
        if not self._use_primary():
            try:
                return await self.fallback.complete_grounded(prompt, system=system)
            except LLMError:
                return await self.primary.complete_grounded(prompt, system=system)
        try:
            return await self.primary.complete_grounded(prompt, system=system)
        except LLMError as exc:
            self._mark_down(exc)
            return await self.fallback.complete_grounded(prompt, system=system)

    def _mark_down(self, exc: LLMError) -> None:
        message = str(exc)
        cooldown = 600 if "daily conversation limit" in message or "RESOURCE_EXHAUSTED" in message else 60
        self._exhausted_until = time.time() + cooldown
        print(f"[engine] Gemini down ({cooldown}s cooldown), using Ollama: {message}")