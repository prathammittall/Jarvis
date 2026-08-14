"""Ollama local LLM provider (offline fallback)."""

from __future__ import annotations

from typing import Any

from app.brain.ollama_client import OllamaClient, OllamaError
from app.brain.providers.base import ChatResult, LLMError, LLMProvider
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("provider.ollama")


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, client: OllamaClient | None = None) -> None:
        self._client = client or OllamaClient()

    @property
    def client(self) -> OllamaClient:
        return self._client

    def is_available(self) -> bool:
        if not get_settings().ollama_enabled:
            return False
        return self._client.is_running()

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        format_json: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        # Ollama path uses JSON schema in prompts; native tools optional later
        try:
            import time
            start = time.perf_counter()
            content = self._client.chat(
                messages,
                temperature=temperature,
                format_json=format_json,
            )
            elapsed = time.perf_counter() - start
            model = ""
            try:
                model = self._client.resolve_model()
            except Exception:
                pass
            return ChatResult(
                content=content,
                provider=self.name,
                model=model,
                elapsed=elapsed,
            )
        except OllamaError as e:
            raise LLMError(str(e)) from e

    def warmup(self) -> dict[str, Any]:
        return self._client.warmup()
