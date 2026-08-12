"""xAI Grok API provider (OpenAI-compatible chat completions)."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from app.brain.providers.base import ChatResult, LLMError, LLMProvider
from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("provider.grok")


def _tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Jarvis tool schemas to OpenAI function-calling format."""
    out = []
    for t in tools:
        params = t.get("parameters") or {}
        # Ensure JSON-schema object shape
        if "type" not in params:
            properties = {}
            required = []
            for key, meta in params.items():
                if isinstance(meta, dict):
                    properties[key] = meta
                else:
                    properties[key] = {"type": "string", "description": str(meta)}
            params = {"type": "object", "properties": properties, "required": required}
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": params,
            },
        })
    # Always allow a spoken-only respond function
    out.append({
        "type": "function",
        "function": {
            "name": "respond",
            "description": "Speak a short reply without running a desktop tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "response": {"type": "string", "description": "Short spoken reply"},
                },
                "required": ["response"],
            },
        },
    })
    return out


class GrokProvider(LLMProvider):
    name = "grok"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = (settings.grok_api_key or "").strip()
        self._base_url = (settings.grok_base_url or "https://api.x.ai/v1").rstrip("/")
        self._model = settings.grok_model or "grok-3-mini"
        self._timeout = float(settings.grok_timeout)
        self._enabled = bool(settings.grok_enabled)
        self._available: bool | None = None
        self._session = requests.Session()

    def is_available(self) -> bool:
        if not self._enabled:
            return False
        if not self._api_key:
            return False
        if self._available is False:
            return False
        return True

    def mark_unavailable(self) -> None:
        self._available = False

    def mark_available(self) -> None:
        self._available = True

    def health_check(self) -> dict[str, Any]:
        result = {
            "provider": self.name,
            "enabled": self._enabled,
            "configured": bool(self._api_key),
            "available": False,
            "model": self._model,
            "error": None,
        }
        if not self._enabled:
            result["error"] = "Grok disabled"
            self._available = False
            return result
        if not self._api_key:
            result["error"] = "GROK_API_KEY not set"
            self._available = False
            return result
        try:
            r = self._session.get(
                f"{self._base_url}/models",
                headers=self._headers(),
                timeout=min(5.0, self._timeout),
            )
            if r.status_code == 200:
                self._available = True
                result["available"] = True
            else:
                self._available = False
                result["error"] = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            self._available = False
            result["error"] = str(e)
        return result

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        format_json: bool = False,
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        if not self.is_available():
            raise LLMError("Grok is not available (disabled, missing key, or marked offline).")

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            "max_tokens": 512,
        }
        if tools:
            payload["tools"] = _tools_to_openai(tools)
            payload["tool_choice"] = "auto"
        elif format_json:
            payload["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            r = self._session.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self._timeout,
            )
            elapsed = time.perf_counter() - start
            if r.status_code >= 400:
                # Network/auth failures mark unavailable for this session soft-state
                if r.status_code in (401, 403, 429) or r.status_code >= 500:
                    self._available = False
                raise LLMError(f"Grok HTTP {r.status_code}: {r.text[:200]}")

            data = r.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = (message.get("content") or "").strip()

            tool_name = None
            tool_arguments: dict[str, Any] = {}
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                call = tool_calls[0]
                fn = call.get("function") or {}
                tool_name = fn.get("name")
                raw_args = fn.get("arguments") or "{}"
                try:
                    tool_arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except json.JSONDecodeError:
                    tool_arguments = {}

            usage = data.get("usage") or {}
            self._available = True
            logger.info(
                "Grok: model=%s elapsed=%.2fs tools=%s usage=%s",
                self._model,
                elapsed,
                tool_name or "none",
                {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage},
            )
            return ChatResult(
                content=content,
                provider=self.name,
                model=self._model,
                elapsed=elapsed,
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                usage=usage,
                raw=data,
            )
        except requests.Timeout as e:
            elapsed = time.perf_counter() - start
            logger.warning("Grok request failed after %.2fs (timeout)", elapsed)
            self._available = False
            raise LLMError(f"Grok timed out after {self._timeout}s") from e
        except requests.RequestException as e:
            elapsed = time.perf_counter() - start
            logger.warning("Grok request failed after %.2fs: %s", elapsed, e)
            self._available = False
            raise LLMError(f"Grok request failed: {e}") from e

    def warmup(self) -> dict[str, Any]:
        start = time.perf_counter()
        health = self.health_check()
        health["elapsed"] = time.perf_counter() - start
        if health.get("available"):
            logger.info("Grok health check OK (model=%s, %.2fs)", self._model, health["elapsed"])
        else:
            logger.info("Grok unavailable: %s", health.get("error"))
        return health
