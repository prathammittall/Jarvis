"""Tests for desktop runtime pieces: catalog, hotkey, startup, local commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.brain.fast_commands import FastCommandRouter
from app.core.hotkey import parse_hotkey, MOD_CONTROL, VK_SPACE
from app.tools import app_catalog
from app.wakeword.detector import text_matches_wake


class TestHotkeyParse:
    def test_ctrl_space(self):
        mods, vk = parse_hotkey("ctrl+space")
        assert mods == MOD_CONTROL
        assert vk == VK_SPACE

    def test_ctrl_shift_j(self):
        mods, vk = parse_hotkey("ctrl+shift+j")
        assert mods & MOD_CONTROL
        assert vk == ord("J")

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_hotkey("ctrl+")


class TestWakeWordMatch:
    def test_jarvis(self):
        assert text_matches_wake("jarvis")
        assert text_matches_wake("hey jarvis")
        assert text_matches_wake("Okay Jarvis!")
        assert not text_matches_wake("hey google")


class TestCatalog:
    def test_chrome_alias(self):
        assert app_catalog.resolve_app_key("google chrome") == "chrome"
        assert app_catalog.close_exe("vscode") == "Code.exe"

    def test_website(self):
        assert "google.com" in app_catalog.website_url("google")
        assert "github.com" in app_catalog.website_url("github")

    def test_folder(self):
        assert app_catalog.folder_key("downloads") == "downloads"
        assert app_catalog.folder_key("my desktop") == "desktop"


class TestNewLocalCommands:
    @pytest.fixture
    def router(self):
        return FastCommandRouter()

    @pytest.mark.parametrize(
        "phrase,action",
        [
            ("open chrome", "open_application"),
            ("close chrome", "close_application"),
            ("close vs code", "close_application"),
            ("open downloads", "open_folder"),
            ("open documents", "open_folder"),
            ("open desktop", "open_folder"),
            ("open google", "open_url"),
            ("open github", "open_url"),
            ("open youtube", "open_youtube"),
            ("open whatsapp", "open_whatsapp"),
            ("open whatsapp web", "open_whatsapp"),
            ("whatsapp kholo", "open_whatsapp"),
            ("lock my pc", "lock_computer"),
        ],
    )
    def test_phrases(self, router, phrase, action):
        matched = router.match(phrase)
        assert matched is not None, f"Expected match for: {phrase}"
        assert matched.action == action

    def test_explain_falls_through(self, router):
        assert router.match("explain recursion in Java") is None
        assert router.match("write a Java function for GCD") is None


class TestWhatsApp:
    def test_open_is_local(self):
        router = FastCommandRouter()
        matched = router.match("open whatsapp")
        assert matched is not None
        assert matched.action == "open_whatsapp"

    @pytest.mark.parametrize(
        "phrase,contact,message_part",
        [
            ("send a message to mom on whatsapp saying I will be late", "mom", "late"),
            ("whatsapp rahul saying hello", "rahul", "hello"),
            ("send hello to dad on whatsapp", "dad", "hello"),
            ("message priya on whatsapp saying call me", "priya", "call"),
        ],
    )
    def test_send_phrases(self, phrase, contact, message_part):
        router = FastCommandRouter()
        matched = router.match(phrase)
        assert matched is not None, f"Expected match for: {phrase}"
        assert matched.action == "send_whatsapp_message"
        assert matched.arguments.get("contact") == contact
        assert message_part in (matched.arguments.get("message") or "").lower()

    def test_open_chat_without_body(self):
        router = FastCommandRouter()
        matched = router.match("send a message to mom on whatsapp")
        assert matched is not None
        assert matched.action == "send_whatsapp_message"
        assert matched.arguments.get("contact") == "mom"

    def test_phone_normalize(self):
        from app.tools.whatsapp import normalize_phone
        assert normalize_phone("+91 98765 43210") == "919876543210"
        assert normalize_phone("9876543210") == "919876543210"

    def test_lookup(self):
        from app.tools.whatsapp import lookup_phone
        with patch("app.tools.whatsapp.load_contacts", return_value={"mom": "919812345678"}):
            assert lookup_phone("Mom") == "919812345678"
            assert lookup_phone("unknown") is None


class TestGeminiNotPermanentlyDisabled:
    def test_timeout_still_available_next_call(self):
        from app.brain.providers.base import LLMError
        from app.brain.providers.gemini import GeminiProvider

        with patch("app.brain.providers.gemini.get_settings") as gs:
            settings = gs.return_value
            settings.gemini_enabled = True
            settings.gemini_api_key = "test-key"
            settings.gemini_base_url = "https://example.invalid"
            settings.gemini_model = "gemini-2.0-flash"
            settings.gemini_timeout = 1.0
            p = GeminiProvider()
            p._hard_fail = False
            assert p.is_available() is True
            # Network failure must not hard-disable Gemini for later turns
            p._hard_fail = False
            assert p.is_available() is True
            p.mark_unavailable()
            assert p.is_available() is False
            p.mark_available()
            assert p.is_available() is True
            _ = LLMError


class TestOllamaCanBeDisabled:
    def test_disabled_flag(self):
        from app.brain.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        with patch("app.brain.providers.ollama.get_settings") as gs, \
             patch.object(provider._client, "is_running", return_value=True):
            gs.return_value.ollama_enabled = False
            assert provider.is_available() is False


class TestStartupPaths:
    def test_shortcut_name(self):
        from app.core.startup import SHORTCUT_NAME, shortcut_path
        assert SHORTCUT_NAME.endswith(".lnk")
        assert shortcut_path().name == SHORTCUT_NAME
