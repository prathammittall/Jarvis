"""Provider factory and failover chain."""

from __future__ import annotations

from typing import Any

from app.brain.providers.base import ChatResult, LLMError, LLMProvider
from app.brain.providers.gemini import GeminiProvider
from app.brain.providers.ollama import OllamaProvider
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("providers")


class ProviderChain:
    """Try Gemini first (if enabled), then Ollama."""

    def __init__(self) -> None:
        self.gemini = GeminiProvider()
        self.ollama = OllamaProvider()
        self._settings = get_settings()

    def primary_name(self) -> str:
        if self.gemini.is_available():
            return "gemini"
        if self.ollama.is_available():
            return "ollama"
        return "none"

    def any_available(self) -> bool:
        return self.gemini.is_available() or self.ollama.is_available()

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        format_json: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        errors: list[str] = []

        if self._settings.gemini_enabled and self.gemini.is_available():
            try:
                return self.gemini.chat(
                    messages,
                    temperature=temperature,
                    format_json=format_json,
                    tools=tools,
                )
            except LLMError as e:
                msg = str(e)
                errors.append(f"gemini: {msg}")
                logger.warning("Gemini unavailable — falling back to Ollama. (%s)", msg)

        if self.ollama.is_available():
            try:
                # Ollama uses JSON prompt path; ignore native tools list
                return self.ollama.chat(
                    messages,
                    temperature=temperature,
                    format_json=format_json or bool(tools),
                    tools=None,
                )
            except LLMError as e:
                errors.append(f"ollama: {e}")

        raise LLMError(
            "No LLM provider available. "
            + ("; ".join(errors) if errors else "Configure GEMINI_API_KEY or start Ollama.")
        )

    def warmup_all(self) -> None:
        if self._settings.gemini_enabled:
            try:
                self.gemini.warmup()
            except Exception as e:
                logger.warning("Gemini warmup error: %s", e)
        if self._settings.ollama_enabled and self._settings.ollama_warmup_enabled:
            try:
                self.ollama.warmup()
            except Exception as e:
                logger.warning("Ollama warmup error: %s", e)


_chain: ProviderChain | None = None


def get_provider_chain() -> ProviderChain:
    global _chain
    if _chain is None:
        _chain = ProviderChain()
    return _chain
