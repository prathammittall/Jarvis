"""LLM provider abstraction for JARVIS."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatResult:
    content: str = ""
    provider: str = ""
    model: str = ""
    elapsed: float = 0.0
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None

    @property
    def has_tool_call(self) -> bool:
        return bool(self.tool_name)


class LLMError(Exception):
    """Provider request failed."""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        format_json: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        ...

    def warmup(self) -> dict[str, Any]:
        return {"success": False, "provider": self.name, "error": "warmup not implemented"}

    def close(self) -> None:
        return None
