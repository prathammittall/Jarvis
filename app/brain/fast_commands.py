"""Deterministic fast command router — bypasses LLM for common commands.

Pipeline:
  speech text → language detect → normalize → phrase match / pattern intent → tool
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.brain.language import Language, detect_language, language_label
from app.brain.normalize import (
    INTENT_UNKNOWN,
    intent_to_tool_call,
    normalize_verbs,
    parse_intent,
    strip_wake_word,
)
from app.brain.responses import error_response, format_response
from app.config import PROJECT_ROOT, get_settings
from app.core.logger import get_logger
from app.tools.registry import RiskLevel, get_registry

logger = get_logger("fast_commands")

COMPLEX_MARKERS = (
    " and ", " aur ", " then ", " also ", " plus ",
    " analyze ", " analyse ", " explain ", " why ", " how to ",
    " tell me about ", " what do you think ", " summarize ",
    " write ", " create a script ", " refactor ",
)

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
    intent: str = ""
    language: Language = Language.ENGLISH
    normalized: str = ""
    target: str = ""


# Backwards-compatible alias used by tests
def normalize_command(text: str, jarvis_name: str = "jarvis") -> str:
    """Lowercase, strip punctuation/wake-word, collapse whitespace, normalize verbs."""
    stripped = strip_wake_word(text, jarvis_name)
    return normalize_verbs(stripped)


def _looks_complex(text: str) -> bool:
    padded = f" {text} "
    if any(m in padded for m in COMPLEX_MARKERS):
        return True
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
            raw_phrases = [p for p in item.get("phrases", []) if p]
            # Store both original-normalized and verb-normalized forms
            phrases: list[str] = []
            for p in raw_phrases:
                n = normalize_command(p)
                if n and n not in phrases:
                    phrases.append(n)
            cmd = FastCommand(
                name=item.get("name", ""),
                action=item["action"],
                arguments=item.get("arguments") or {},
                response=item.get("response") or "",
                phrases=phrases,
                intent=item.get("intent") or "",
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

    def _from_phrase(self, matched: FastCommand, language: Language, normalized: str) -> FastCommand:
        target = (
            matched.arguments.get("application")
            or matched.arguments.get("query")
            or matched.arguments.get("project")
            or ""
        )
        intent = matched.intent or _guess_intent(matched.action, matched.arguments)
        response = matched.response
        if intent:
            localized = format_response(intent, language, target=str(target), fallback=response)
            if localized:
                response = localized
        return FastCommand(
            name=matched.name,
            action=matched.action,
            arguments=dict(matched.arguments),
            response=response,
            phrases=matched.phrases,
            confidence=1.0,
            intent=intent,
            language=language,
            normalized=normalized,
            target=str(target),
        )

    def match(self, command: str) -> FastCommand | None:
        if not self._enabled:
            return None

        stripped = strip_wake_word(command, self._jarvis_name)
        if not stripped:
            return None

        language = detect_language(stripped)
        normalized = normalize_verbs(stripped)

        if _looks_complex(normalized) and _looks_complex(stripped):
            logger.debug("Fast router skip (complex): %r", normalized)
            return None

        # 1) Exact phrase match on normalized text
        if normalized in self._phrase_map:
            return self._from_phrase(self._phrase_map[normalized], language, normalized)

        # Also try stripped without verb expand (config may list hinglish literally)
        light = strip_wake_word(command, self._jarvis_name)
        light = re.sub(r"[^\w\s\u0900-\u097F]", " ", light.lower())
        light = re.sub(r"\s+", " ", light).strip()
        if light in self._phrase_map:
            return self._from_phrase(self._phrase_map[light], language, normalized)

        # 2) Pattern / intent parser (handles natural variations)
        parsed = parse_intent(command, self._jarvis_name)
        if parsed.intent != INTENT_UNKNOWN and parsed.confidence >= 0.85:
            tool_call = intent_to_tool_call(parsed)
            if tool_call:
                action, arguments = tool_call
                target = parsed.target or arguments.get("application") or arguments.get("query") or ""
                response = format_response(parsed.intent, language, target=str(target))
                return FastCommand(
                    name=f"intent:{parsed.intent}",
                    action=action,
                    arguments=arguments,
                    response=response,
                    confidence=parsed.confidence,
                    intent=parsed.intent,
                    language=language,
                    normalized=parsed.normalized or normalized,
                    target=str(target),
                )

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
                result = self._from_phrase(best, language, normalized)
                result.confidence = best_ratio
                return result

        return None

    def execute(self, command: str) -> dict[str, Any] | None:
        """
        Match and execute via the tool registry.
        Returns None if no match (caller should fall through to LLM).
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

        debug_info = {
            "speech": command,
            "language": language_label(matched.language),
            "normalized": matched.normalized,
            "intent": matched.intent or matched.name,
            "target": matched.target,
            "action": matched.action,
            "confidence": matched.confidence,
        }

        logger.info(
            "Fast router: matched '%s' -> %s (lang=%s, confidence=%.2f, %.3fs)",
            matched.name,
            matched.action,
            debug_info["language"],
            matched.confidence,
            elapsed,
        )

        if needs_confirmation and settings.confirm_dangerous_actions:
            # Require high confidence for destructive power actions
            if matched.action == "system_power" and matched.confidence < 0.85:
                return None
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
                "language": matched.language.value,
                "intent": matched.intent,
                "normalized": matched.normalized,
                "debug": debug_info,
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

        if not result.get("success"):
            err = result.get("error", "")
            if "could not find" in err.lower() or "not found" in err.lower():
                response = error_response("app_not_found", matched.language)
            else:
                response = matched.response or err or error_response("not_understood", matched.language)
        else:
            response = matched.response or result.get("message") or (
                "Done." if result.get("success") else result.get("error", "Failed.")
            )
            # Prefer live tool message for info queries (time, CPU, etc.)
            if not matched.response and result.get("message"):
                response = result["message"]
            elif matched.intent == "GET_TIME" and result.get("message"):
                response = result["message"]

        debug_info["execution"] = "SUCCESS" if result.get("success") else "FAILED"
        debug_info["latency_s"] = round(elapsed + tool_elapsed, 3)

        return {
            "success": result.get("success", False),
            "response": response,
            "tool": matched.action,
            "arguments": matched.arguments,
            "result": result,
            "source": "fast",
            "fast_command": matched.name,
            "language": matched.language.value,
            "intent": matched.intent,
            "normalized": matched.normalized,
            "debug": debug_info,
            "timings": {
                "fast_router": elapsed,
                "tool_execution": tool_elapsed,
                "total": elapsed + tool_elapsed,
            },
        }


def _guess_intent(action: str, arguments: dict[str, Any]) -> str:
    if action == "open_application":
        return "OPEN_APP"
    if action == "close_application":
        return "CLOSE_APP"
    if action == "open_youtube":
        return "OPEN_WEBSITE"
    if action == "google_search":
        return "SEARCH_WEB"
    if action == "volume_control":
        a = (arguments.get("action") or "").lower()
        return {
            "up": "INCREASE_VOLUME",
            "down": "DECREASE_VOLUME",
            "mute": "MUTE",
            "unmute": "UNMUTE",
        }.get(a, "INCREASE_VOLUME")
    if action == "media_control":
        a = (arguments.get("action") or "").lower()
        return {
            "play": "PLAY_MEDIA",
            "pause": "PAUSE_MEDIA",
            "stop": "STOP_MEDIA",
            "next": "NEXT_TRACK",
            "previous": "PREV_TRACK",
        }.get(a, "PLAY_MEDIA")
    if action == "system_power":
        a = (arguments.get("action") or "").lower()
        return {"shutdown": "SHUTDOWN", "restart": "RESTART", "sleep": "SLEEP"}.get(a, "SHUTDOWN")
    if action == "lock_computer":
        return "LOCK_PC"
    if action == "take_screenshot":
        return "TAKE_SCREENSHOT"
    if action == "create_folder":
        return "CREATE_FOLDER"
    if action == "get_time":
        return "GET_TIME"
    return ""


_router: FastCommandRouter | None = None


def get_fast_router() -> FastCommandRouter:
    global _router
    if _router is None:
        _router = FastCommandRouter()
    return _router
