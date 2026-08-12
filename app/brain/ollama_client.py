"""Ollama API client for local LLM inference."""

from __future__ import annotations

import re
import time
from typing import Any

import requests

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("ollama")

PREFERRED_MODELS = [
    "qwen3:4b",
    "qwen2.5:3b",
    "llama3.2:3b",
    "phi3:mini",
    "gemma2:2b",
    "mistral:7b",
    "llama3.1:8b",
]

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


class OllamaError(Exception):
    pass


def _parse_keep_alive(value: str | int | None) -> str | int:
    """Accept -1, 0, seconds, or duration strings like '30m'."""
    if value is None or value == "":
        return -1
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return text


class OllamaClient:
    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or settings.ollama_model
        self.keep_alive = _parse_keep_alive(settings.ollama_keep_alive)
        self.timeout = float(settings.ollama_timeout)
        self._session = requests.Session()

    def is_running(self) -> bool:
        try:
            r = self._session.get(f"{self.host}/api/tags", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        try:
            r = self._session.get(f"{self.host}/api/tags", timeout=10)
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except requests.RequestException as e:
            logger.error("Failed to list models: %s", e)
            return []

    def resolve_model(self) -> str:
        if self.model:
            models = self.list_models()
            if self.model in models:
                return self.model
            for m in models:
                if m.startswith(self.model) or self.model.startswith(m.split(":")[0]):
                    return m

        models = self.list_models()
        if not models:
            raise OllamaError("No Ollama models installed.")

        for preferred in PREFERRED_MODELS:
            for m in models:
                if m == preferred or m.startswith(preferred.split(":")[0]):
                    return m

        return models[0]

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        format_json: bool = False,
        keep_alive: str | int | None = None,
    ) -> str:
        model = self.resolve_model()
        ka = self.keep_alive if keep_alive is None else _parse_keep_alive(keep_alive)

        # Approximate prompt size for logging
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        approx_tokens = max(1, prompt_chars // 4)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": ka,
            # qwen3 thinking models often leave content empty unless think is disabled
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": 256,
            },
        }
        if format_json:
            payload["format"] = "json"

        start = time.perf_counter()
        try:
            r = self._session.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            message = data.get("message", {}) or {}
            content = (message.get("content") or "").strip()
            content = _THINK_RE.sub("", content).strip()

            # Fallback: extract JSON from thinking field if content empty
            if not content:
                thinking = message.get("thinking") or ""
                match = re.search(r"\{[\s\S]*\}", thinking)
                if match:
                    content = match.group(0).strip()

            elapsed = time.perf_counter() - start
            eval_count = data.get("eval_count")
            logger.info(
                "Ollama: model=%s keep_alive=%s ~%d tokens prompt, response=%.2fs%s",
                model,
                ka,
                approx_tokens,
                elapsed,
                f", eval_count={eval_count}" if eval_count is not None else "",
            )

            if not content and format_json:
                retry_messages = list(messages) + [
                    {
                        "role": "user",
                        "content": (
                            'Reply with JSON only: '
                            '{"action":"respond","arguments":{},"response":"Done.","needs_confirmation":false}'
                        ),
                    }
                ]
                payload["messages"] = retry_messages
                r2 = self._session.post(
                    f"{self.host}/api/chat", json=payload, timeout=self.timeout,
                )
                r2.raise_for_status()
                message2 = r2.json().get("message", {}) or {}
                content = _THINK_RE.sub("", (message2.get("content") or "")).strip()
                if not content:
                    thinking = message2.get("thinking") or ""
                    match = re.search(r"\{[\s\S]*\}", thinking)
                    if match:
                        content = match.group(0).strip()
            return content.strip()
        except requests.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature)

    def warmup(self) -> dict[str, Any]:
        """Load the model into memory and keep it loaded (non-conversational)."""
        result: dict[str, Any] = {"success": False, "elapsed": 0.0, "model": None, "error": None}
        if not self.is_running():
            result["error"] = "Ollama server is not reachable."
            return result

        start = time.perf_counter()
        logger.info("Ollama warmup started")
        try:
            model = self.resolve_model()
            result["model"] = model
            # Minimal generate request with keep_alive=-1 to pin model in VRAM
            payload = {
                "model": model,
                "prompt": "ping",
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {"num_predict": 1, "temperature": 0},
            }
            r = self._session.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            elapsed = time.perf_counter() - start
            result["success"] = True
            result["elapsed"] = elapsed
            logger.info("Ollama warmup completed in %.2fs (model=%s, keep_alive=%s)", elapsed, model, self.keep_alive)
        except Exception as e:
            elapsed = time.perf_counter() - start
            result["elapsed"] = elapsed
            result["error"] = str(e)
            logger.warning("Ollama warmup failed after %.2fs: %s", elapsed, e)
        return result

    def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "running": False,
            "models": [],
            "selected_model": None,
            "keep_alive": self.keep_alive,
            "error": None,
        }
        if not self.is_running():
            result["error"] = "Ollama server is not reachable."
            return result

        result["running"] = True
        result["models"] = self.list_models()
        try:
            result["selected_model"] = self.resolve_model()
        except OllamaError as e:
            result["error"] = str(e)
        return result
