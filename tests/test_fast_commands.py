"""Tests for fast command routing and Ollama keep-alive config."""

from __future__ import annotations

import time

import pytest

from app.brain.fast_commands import FastCommandRouter, normalize_command
from app.brain.ollama_client import _parse_keep_alive
from app.tools.registry import get_registry


@pytest.fixture
def router():
    return FastCommandRouter()


class TestNormalize:
    def test_strips_wake_word(self):
        assert normalize_command("Jarvis, open Chrome") == "open chrome"
        assert normalize_command("hey jarvis open vscode") == "open vscode"

    def test_collapses_space_and_punct(self):
        assert normalize_command("  Open   Chrome!!! ") == "open chrome"


class TestFastRouterMatching:
    @pytest.mark.parametrize(
        "phrase,action,app",
        [
            ("open chrome", "open_application", "chrome"),
            ("chrome kholo", "open_application", "chrome"),
            ("chrome khol de", "open_application", "chrome"),
            ("launch chrome", "open_application", "chrome"),
            ("open vscode", "open_application", "vscode"),
            ("open visual studio code", "open_application", "vscode"),
            ("vs code kholo", "open_application", "vscode"),
            ("open spotify", "open_application", "spotify"),
            ("volume up", "volume_control", None),
            ("increase volume", "volume_control", None),
            ("mute", "volume_control", None),
            ("unmute", "volume_control", None),
            ("pause music", "media_control", None),
            ("play music", "media_control", None),
            ("take a screenshot", "take_screenshot", None),
            ("lock my pc", "lock_computer", None),
            ("Jarvis open chrome", "open_application", "chrome"),
        ],
    )
    def test_common_phrases(self, router, phrase, action, app):
        matched = router.match(phrase)
        assert matched is not None, f"Expected match for: {phrase}"
        assert matched.action == action
        if app:
            assert matched.arguments.get("application") == app

    def test_complex_falls_through(self, router):
        assert router.match("open chrome and analyze my project structure") is None
        assert router.match("tell me about Chrome browser history") is None

    def test_shutdown_requires_confirmation_path(self, router):
        result = router.execute("shutdown the computer")
        assert result is not None
        assert result.get("awaiting_confirmation") is True
        assert result.get("source") == "fast"
        assert result["pending_action"]["action"] == "system_power"


class TestFastRouterNoOllama:
    def test_open_chrome_source_fast(self, router):
        # Don't actually launch if possible — execute goes through registry.
        # We only assert routing metadata for a volume command (safe + fast).
        result = router.execute("mute")
        assert result is not None
        assert result["source"] == "fast"
        assert result["tool"] == "volume_control"
        assert "ollama" not in result.get("timings", {})

    def test_fast_is_quick(self, router):
        start = time.perf_counter()
        matched = router.match("open chrome")
        elapsed = time.perf_counter() - start
        assert matched is not None
        assert elapsed < 0.05  # deterministic match should be near-instant


class TestKeepAlive:
    def test_parse_keep_alive(self):
        assert _parse_keep_alive("-1") == -1
        assert _parse_keep_alive(-1) == -1
        assert _parse_keep_alive("0") == 0
        assert _parse_keep_alive("30m") == "30m"
        assert _parse_keep_alive(None) == -1


class TestMediaToolRegistered:
    def test_media_control_exists(self):
        registry = get_registry()
        tool = registry.get("media_control")
        assert tool is not None
        assert tool.name == "media_control"
