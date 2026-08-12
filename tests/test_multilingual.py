"""Multilingual intent tests: English, Hindi, Hinglish."""

from __future__ import annotations

import time

import pytest

from app.brain.fast_commands import FastCommandRouter, normalize_command
from app.brain.language import Language, detect_language, language_label
from app.brain.normalize import (
    INTENT_CREATE_FOLDER,
    INTENT_DECREASE_VOLUME,
    INTENT_INCREASE_VOLUME,
    INTENT_OPEN_APP,
    INTENT_OPEN_WEBSITE,
    INTENT_PLAY_MEDIA,
    INTENT_SEARCH_WEB,
    INTENT_SHUTDOWN,
    intent_to_tool_call,
    normalize_verbs,
    parse_intent,
)
from app.brain.responses import format_response


@pytest.fixture
def router():
    return FastCommandRouter()


class TestLanguageDetection:
    def test_english(self):
        assert detect_language("Open Chrome") == Language.ENGLISH
        assert detect_language("Increase volume") == Language.ENGLISH

    def test_hindi_devanagari(self):
        assert detect_language("क्रोम खोलो") == Language.HINDI
        assert detect_language("मुझे YouTube खोलना है") == Language.HINDI

    def test_hinglish(self):
        assert detect_language("Chrome kholo") == Language.HINGLISH
        assert detect_language("Chrome open karo") == Language.HINGLISH
        assert detect_language("Volume badha do") == Language.HINGLISH

    def test_labels(self):
        assert language_label(Language.HINGLISH) == "HINGLISH"


class TestNormalization:
    @pytest.mark.parametrize(
        "raw,expected_substr",
        [
            ("Chrome kholo", "open"),
            ("Chrome khol do", "open"),
            ("Chrome open karo", "open"),
            ("Chrome ko kholo", "open"),
            ("Volume badha do", "increase"),
            ("Volume kam karo", "decrease"),
            ("music chalao", "play"),
        ],
    )
    def test_verb_normalize(self, raw, expected_substr):
        out = normalize_verbs(raw.lower())
        assert expected_substr in out

    def test_normalize_command_strips_wake(self):
        assert "chrome" in normalize_command("Jarvis Chrome kholo")
        assert "open" in normalize_command("Jarvis Chrome kholo")


class TestParseIntentEnglish:
    @pytest.mark.parametrize(
        "phrase,intent,target",
        [
            ("Open Chrome", INTENT_OPEN_APP, "chrome"),
            ("Open YouTube", INTENT_OPEN_WEBSITE, "youtube"),
            ("Increase volume", INTENT_INCREASE_VOLUME, ""),
            ("Decrease volume", INTENT_DECREASE_VOLUME, ""),
            ("Shutdown computer", INTENT_SHUTDOWN, ""),
            ("search for Java tutorials", INTENT_SEARCH_WEB, "java tutorials"),
        ],
    )
    def test_english_intents(self, phrase, intent, target):
        parsed = parse_intent(phrase)
        assert parsed.intent == intent, f"{phrase} -> {parsed.intent}"
        if target:
            assert target.lower() in (parsed.target or "").lower() or target.lower() in str(
                parsed.parameters.get("query", "")
            ).lower()


class TestParseIntentHindi:
    @pytest.mark.parametrize(
        "phrase,intent",
        [
            ("क्रोम खोलो", INTENT_OPEN_APP),
            ("यूट्यूब खोलो", INTENT_OPEN_WEBSITE),
            ("वॉल्यूम बढ़ा दो", INTENT_INCREASE_VOLUME),
            ("वॉल्यूम कम कर दो", INTENT_DECREASE_VOLUME),
            ("कंप्यूटर बंद कर दो", INTENT_SHUTDOWN),
        ],
    )
    def test_hindi_intents(self, phrase, intent):
        parsed = parse_intent(phrase)
        assert parsed.intent == intent, f"{phrase} -> {parsed.intent} norm={parsed.normalized}"
        assert parsed.language == Language.HINDI


class TestParseIntentHinglish:
    @pytest.mark.parametrize(
        "phrase,intent,check",
        [
            ("Chrome kholo", INTENT_OPEN_APP, "chrome"),
            ("Chrome open karo", INTENT_OPEN_APP, "chrome"),
            ("YouTube chalao", INTENT_OPEN_WEBSITE, "youtube"),
            ("YouTube play karo", INTENT_OPEN_WEBSITE, "youtube"),
            ("YouTube kholo", INTENT_OPEN_WEBSITE, "youtube"),
            ("Volume badha do", INTENT_INCREASE_VOLUME, None),
            ("Volume kam karo", INTENT_DECREASE_VOLUME, None),
            ("Computer shutdown karo", INTENT_SHUTDOWN, None),
            ("Google pe Python search karo", INTENT_SEARCH_WEB, "python"),
            ("Notepad kholo", INTENT_OPEN_APP, "notepad"),
            ("music chalao", INTENT_PLAY_MEDIA, None),
            ("ek folder banao", INTENT_CREATE_FOLDER, None),
            ("Chrome mein YouTube open karo", INTENT_OPEN_WEBSITE, "youtube"),
            ("mera laptop shutdown karo", INTENT_SHUTDOWN, None),
        ],
    )
    def test_hinglish_intents(self, phrase, intent, check):
        parsed = parse_intent(f"Jarvis, {phrase}")
        assert parsed.intent == intent, f"{phrase} -> {parsed.intent} norm={parsed.normalized}"
        if check:
            blob = f"{parsed.target} {parsed.parameters}".lower()
            assert check in blob


class TestRouterMultilingual:
    @pytest.mark.parametrize(
        "phrase,action",
        [
            ("Open Chrome", "open_application"),
            ("Chrome kholo", "open_application"),
            ("Chrome open karo", "open_application"),
            ("क्रोम खोलो", "open_application"),
            ("Open YouTube", "open_youtube"),
            ("YouTube kholo", "open_youtube"),
            ("YouTube chalao", "open_youtube"),
            ("Increase volume", "volume_control"),
            ("Volume badha do", "volume_control"),
            ("वॉल्यूम बढ़ा दो", "volume_control"),
            ("Volume kam karo", "volume_control"),
            ("Notepad kholo", "open_application"),
            ("music chalao", "media_control"),
            ("Google pe Python search karo", "google_search"),
            ("Shutdown computer", "system_power"),
            ("Computer shutdown karo", "system_power"),
            ("कंप्यूटर बंद कर दो", "system_power"),
        ],
    )
    def test_router_match(self, router, phrase, action):
        matched = router.match(phrase)
        assert matched is not None, f"No match for: {phrase}"
        assert matched.action == action

    def test_search_query_extracted(self, router):
        matched = router.match("Google pe Python search karo")
        assert matched is not None
        assert matched.action == "google_search"
        assert "python" in matched.arguments.get("query", "").lower()

    def test_localized_response_hinglish(self, router):
        matched = router.match("Chrome kholo")
        assert matched is not None
        assert matched.language == Language.HINGLISH
        assert "open kar raha" in matched.response.lower() or "chrome" in matched.response.lower()

    def test_localized_response_english(self, router):
        matched = router.match("Open Chrome")
        assert matched is not None
        assert matched.language == Language.ENGLISH
        assert "Opening" in matched.response

    def test_localized_response_hindi(self, router):
        matched = router.match("क्रोम खोलो")
        assert matched is not None
        assert matched.language == Language.HINDI
        assert "खोल" in matched.response

    def test_shutdown_confirmation(self, router):
        result = router.execute("mera laptop shutdown karo")
        assert result is not None
        assert result.get("awaiting_confirmation") is True
        assert result["pending_action"]["action"] == "system_power"

    def test_fast_latency(self, router):
        phrases = ["Chrome kholo", "Open Chrome", "Google pe Python search karo"]
        times = []
        for p in phrases:
            t0 = time.perf_counter()
            matched = router.match(p)
            times.append(time.perf_counter() - t0)
            assert matched is not None
        avg = sum(times) / len(times)
        assert avg < 0.05, f"Average match latency too high: {avg:.4f}s"


class TestIntentToolMapping:
    def test_open_app_maps(self):
        parsed = parse_intent("Chrome kholo")
        tool = intent_to_tool_call(parsed)
        assert tool is not None
        assert tool[0] == "open_application"
        assert tool[1]["application"] == "chrome"

    def test_format_response_langs(self):
        assert "Opening" in format_response(INTENT_OPEN_APP, Language.ENGLISH, "chrome")
        assert "खोल" in format_response(INTENT_OPEN_APP, Language.HINDI, "Chrome")
        assert "open kar" in format_response(INTENT_OPEN_APP, Language.HINGLISH, "Chrome").lower()
