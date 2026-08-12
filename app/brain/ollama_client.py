"""Ollama API client for local LLM inference."""

from __future__ import annotations

import json
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


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, host: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or settings.ollama_model
        self._session = requests.Session()
        self._session.timeout = 120

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
            # Try partial match (e.g. qwen3 matches qwen3:4b)
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
        temperature: float = 0.3,
        format_json: bool = False,
    ) -> str:
        model = self.resolve_model()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"

        start = time.perf_counter()
        try:
            r = self._session.post(f"{self.host}/api/chat", json=payload, timeout=120)
            r.raise_for_status()
            content = r.json().get("message", {}).get("content", "")
            elapsed = time.perf_counter() - start
            logger.info("Ollama response in %.2fs (model=%s)", elapsed, model)
            return content.strip()
        except requests.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e

    def generate(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature)

    def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "running": False,
            "models": [],
            "selected_model": None,
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
