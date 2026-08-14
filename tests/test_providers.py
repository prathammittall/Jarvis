"""Tests for Gemini / Ollama provider chain and routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.brain.fast_commands import FastCommandRouter
from app.brain.providers.base import ChatResult, LLMError
from app.brain.providers.gemini import GeminiProvider
from app.brain.providers import ProviderChain


class TestFastStillLocal:
    def test_open_chrome_no_llm(self):
        router = FastCommandRouter()
        matched = router.match("open chrome")
        assert matched is not None
        assert matched.action == "open_application"

    @pytest.mark.parametrize(
        "phrase",
        [
            "chrome kholo",
            "chrome khol de",
            "mera vs code open kar",
            "volume up",
            "mute",
            "open vscode",
        ],
    )
    def test_multilingual_fast(self, phrase):
        router = FastCommandRouter()
        matched = router.match(phrase)
        if phrase in ("chrome kholo", "chrome khol de", "volume up", "mute", "open vscode"):
            assert matched is not None

    def test_agent_fast_path_never_calls_provider(self):
        from app.brain.agent import Agent

        agent = Agent()
        with patch.object(agent._providers, "chat") as mock_chat, \
             patch.object(agent._fast, "execute", return_value={
                 "success": True,
                 "response": "Opening Chrome.",
                 "tool": "open_application",
                 "source": "fast",
                 "timings": {"fast_router": 0.001, "tool_execution": 0.01},
             }):
            result = agent.process_command("open chrome")
            mock_chat.assert_not_called()
            assert result.get("source") == "fast"
            assert result.get("tool") == "open_application"


class TestProviderPriority:
    def test_gemini_primary_when_available(self):
        chain = ProviderChain()
        chain.gemini._enabled = True
        chain.gemini._api_key = "test-key"
        chain.gemini._available = True

        gemini_result = ChatResult(
            content='{"action":"respond","arguments":{},"response":"Hi","needs_confirmation":false}',
            provider="gemini",
            elapsed=0.1,
        )
        with patch.object(chain.gemini, "chat", return_value=gemini_result) as mock_gemini, \
             patch.object(chain.ollama, "is_available", return_value=True), \
             patch.object(chain.ollama, "chat") as mock_ollama:
            out = chain.chat([{"role": "user", "content": "hi"}], format_json=True)
            assert out.provider == "gemini"
            mock_gemini.assert_called_once()
            mock_ollama.assert_not_called()

    def test_fallback_to_ollama_on_gemini_failure(self):
        chain = ProviderChain()
        chain.gemini._enabled = True
        chain.gemini._api_key = "test-key"
        chain.gemini._available = True

        ollama_result = ChatResult(
            content='{"action":"respond","arguments":{},"response":"Ok","needs_confirmation":false}',
            provider="ollama",
            elapsed=0.2,
        )
        with patch.object(chain.gemini, "chat", side_effect=LLMError("timeout")), \
             patch.object(chain.ollama, "is_available", return_value=True), \
             patch.object(chain.ollama, "chat", return_value=ollama_result) as mock_ollama:
            out = chain.chat([{"role": "user", "content": "hi"}], format_json=True)
            assert out.provider == "ollama"
            mock_ollama.assert_called_once()

    def test_gemini_disabled_uses_ollama(self):
        chain = ProviderChain()
        chain.gemini._enabled = False
        chain.gemini._api_key = ""
        ollama_result = ChatResult(content="{}", provider="ollama", elapsed=0.1)
        with patch.object(chain.ollama, "is_available", return_value=True), \
             patch.object(chain.ollama, "chat", return_value=ollama_result):
            out = chain.chat([{"role": "user", "content": "hi"}])
            assert out.provider == "ollama"


class TestGeminiConfig:
    def test_unavailable_without_key(self):
        with patch("app.brain.providers.gemini.get_settings") as gs:
            settings = MagicMock()
            settings.gemini_enabled = True
            settings.gemini_api_key = ""
            settings.gemini_base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            settings.gemini_model = "gemini-2.0-flash"
            settings.gemini_timeout = 10.0
            gs.return_value = settings
            p = GeminiProvider()
            assert p.is_available() is False


class TestSafetyStillApplies:
    def test_shutdown_confirmation(self):
        router = FastCommandRouter()
        result = router.execute("shutdown the computer")
        assert result is not None
        assert result.get("awaiting_confirmation") is True


class TestComplexGoesToLLM:
    def test_analyze_not_fast(self):
        router = FastCommandRouter()
        assert router.match("analyze my project and tell me what needs improvement") is None
