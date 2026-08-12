"""Deterministic fast command router — bypasses Ollama for common commands."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from app.core.logger import get_logger
from app.tools.registry import RiskLevel, get_registry

logger = get_logger("fast_commands")

# Multi-intent / complex connectors → fall through to Ollama
COMPLEX_MARKERS = (
    " and ", " aur ", " then ", " also ", " plus ",
    " analyze ", " analyse ", " explain ", " why ", " how to ",
    " tell me about ", " what do you think ", " summarize ",
    " write ", " create a script ", " refactor ",
)

WAKE_PREFIXES = (
    "jarvis", "hey jarvis", "ok jarvis", "hi jarvis",
)

# Fuzzy match only for short commands; high cutoff avoids false positives
FUZZY_MIN_RATIO = 0.88
FUZZY_MAX_LEN = 40


@dataclass
class FastCommand:
    name: str
    action: str
    arguments: dict[str, Any]
    response: str
    phrases: list[str] = field(default_factory=list)
    confidence: float = 1.0


def normalize_command(text: str, jarvis_name: str = "jarvis") -> str:
    """Lowercase, strip punctuation, wake-word prefix, and collapse whitespace."""
    text = text.lower().strip()
    text = text.replace("'", "'").replace("'", "'")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    prefixes = list(WAKE_PREFIXES) + [jarvis_name.lower()]
    for prefix in sorted(set(prefixes), key=len, reverse=True):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            text = text[len(prefix) + 1 :].strip()
            break
    return text


def _looks_complex(text: str) -> bool:
    padded = f" {text} "
    if any(m in padded for m in COMPLEX_MARKERS):
        return True
    # Long multi-clause utterances are better for the LLM
    if len(text.split()) > 12:
        return True
    return False


class FastCommandRouter:
    def __init__(self, config_path: Path | None = None) -> None:
        settings = get_settings()
        self._enabled = settings.fast_commands_enabled
        self._jarvis_name = settings.jarvis_name
        path = config_path or (PROJECT_ROOT / settings.commands_config)
        self._commands: list[FastCommand] = []
        self._phrase_map: dict[str, FastCommand] = {}
        self._load(path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            logger.warning("Fast commands config not found: %s", path)
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load commands.json: %s", e)
            return

        for item in data.get("commands", []):
            cmd = FastCommand(
                name=item.get("name", ""),
                action=item["action"],
                arguments=item.get("arguments") or {},
                response=item.get("response") or "",
                phrases=[normalize_command(p) for p in item.get("phrases", []) if p],
            )
            if not cmd.action or not cmd.phrases:
                continue
            self._commands.append(cmd)
            for phrase in cmd.phrases:
                self._phrase_map[phrase] = cmd

        logger.info("Loaded %d fast commands (%d phrases)", len(self._commands), len(self._phrase_map))

    def reload(self) -> None:
        settings = get_settings()
        self._commands.clear()
        self._phrase_map.clear()
        self._load(PROJECT_ROOT / settings.commands_config)

    def match(self, command: str) -> FastCommand | None:
        if not self._enabled:
            return None

        normalized = normalize_command(command, self._jarvis_name)
        if not normalized:
            return None
        if _looks_complex(normalized):
            logger.debug("Fast router skip (complex): %r", normalized)
            return None

        # 1) Exact phrase match
        if normalized in self._phrase_map:
            matched = self._phrase_map[normalized]
            return FastCommand(
                name=matched.name,
                action=matched.action,
                arguments=dict(matched.arguments),
                response=matched.response,
                phrases=matched.phrases,
                confidence=1.0,
            )

        # 2) Phrase equals command after light synonym expand (already normalized)
        # 3) Conservative fuzzy match for short STT typos
        if len(normalized) <= FUZZY_MAX_LEN:
            best: FastCommand | None = None
            best_ratio = 0.0
            for phrase, cmd in self._phrase_map.items():
                if abs(len(phrase) - len(normalized)) > 8:
                    continue
                ratio = SequenceMatcher(None, normalized, phrase).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = cmd
            if best and best_ratio >= FUZZY_MIN_RATIO:
                return FastCommand(
                    name=best.name,
                    action=best.action,
                    arguments=dict(best.arguments),
                    response=best.response,
                    phrases=best.phrases,
                    confidence=best_ratio,
                )

        return None

    def execute(self, command: str) -> dict[str, Any] | None:
        """
        Match and execute via the tool registry.
        Returns None if no match (caller should fall through to Ollama).
        Respects tool risk levels / confirmation settings.
        """
        start = time.perf_counter()
        matched = self.match(command)
        elapsed = time.perf_counter() - start

        if matched is None:
            logger.info("Fast router: no match (%.3fs)", elapsed)
            return None

        registry = get_registry()
        tool = registry.get(matched.action)
        if tool is None:
            logger.warning("Fast command '%s' maps to unknown tool '%s'", matched.name, matched.action)
            return None

        settings = get_settings()
        needs_confirmation = tool.risk_level in (
            RiskLevel.CONFIRMATION_REQUIRED,
            RiskLevel.DANGEROUS,
        )

        logger.info(
            "Fast router: matched '%s' -> %s (confidence=%.2f, %.3fs)",
            matched.name,
            matched.action,
            matched.confidence,
            elapsed,
        )

        if needs_confirmation and settings.confirm_dangerous_actions:
            confirm_msg = matched.response or (
                f"This will run {matched.action}. Should I continue?"
            )
            return {
                "success": True,
                "response": confirm_msg,
                "tool": matched.action,
                "arguments": matched.arguments,
                "awaiting_confirmation": True,
                "source": "fast",
                "fast_command": matched.name,
                "pending_action": {
                    "action": matched.action,
                    "arguments": matched.arguments,
                    "response": matched.response,
                },
                "timings": {"fast_router": elapsed},
            }

        tool_start = time.perf_counter()
        result = registry.execute(matched.action, matched.arguments)
        tool_elapsed = time.perf_counter() - tool_start

        response = matched.response or result.get("message") or (
            "Done." if result.get("success") else result.get("error", "Failed.")
        )
        # Prefer live tool message for info queries (time, CPU, etc.)
        if not matched.response and result.get("message"):
            response = result["message"]

        return {
            "success": result.get("success", False),
            "response": response,
            "tool": matched.action,
            "arguments": matched.arguments,
            "result": result,
            "source": "fast",
            "fast_command": matched.name,
            "timings": {
                "fast_router": elapsed,
                "tool_execution": tool_elapsed,
                "total": elapsed + tool_elapsed,
            },
        }


_router: FastCommandRouter | None = None


def get_fast_router() -> FastCommandRouter:
    global _router
    if _router is None:
        _router = FastCommandRouter()
    return _router
