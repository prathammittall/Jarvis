"""Short multilingual spoken responses for Jarvis."""

from __future__ import annotations

from app.brain.language import Language
from app.brain.normalize import (
    INTENT_CLOSE_APP,
    INTENT_CREATE_FOLDER,
    INTENT_DECREASE_VOLUME,
    INTENT_GET_TIME,
    INTENT_INCREASE_VOLUME,
    INTENT_LOCK_PC,
    INTENT_MUTE,
    INTENT_NEXT_TRACK,
    INTENT_OPEN_APP,
    INTENT_OPEN_FOLDER,
    INTENT_OPEN_WEBSITE,
    INTENT_OPEN_WHATSAPP,
    INTENT_PAUSE_MEDIA,
    INTENT_PLAY_MEDIA,
    INTENT_PREV_TRACK,
    INTENT_RESTART,
    INTENT_SEARCH_WEB,
    INTENT_SEND_WHATSAPP,
    INTENT_SHUTDOWN,
    INTENT_SLEEP,
    INTENT_STOP_MEDIA,
    INTENT_TAKE_SCREENSHOT,
    INTENT_UNMUTE,
)

# intent → {en, hi, hinglish}
_TEMPLATES: dict[str, dict[str, str]] = {
    INTENT_OPEN_APP: {
        "en": "Opening {target}.",
        "hi": "{target} खोल रहा हूँ।",
        "hinglish": "{target} open kar raha hoon.",
    },
    INTENT_CLOSE_APP: {
        "en": "Closing {target}.",
        "hi": "{target} बंद कर रहा हूँ।",
        "hinglish": "{target} band kar raha hoon.",
    },
    INTENT_OPEN_WEBSITE: {
        "en": "Opening {target}.",
        "hi": "{target} खोल रहा हूँ।",
        "hinglish": "{target} open kar raha hoon.",
    },
    INTENT_OPEN_FOLDER: {
        "en": "Opening {target}.",
        "hi": "{target} खोल रहा हूँ।",
        "hinglish": "{target} open kar raha hoon.",
    },
    INTENT_OPEN_WHATSAPP: {
        "en": "Opening WhatsApp Web.",
        "hi": "WhatsApp Web खोल रहा हूँ।",
        "hinglish": "WhatsApp Web open kar raha hoon.",
    },
    INTENT_SEND_WHATSAPP: {
        "en": "Sending that to {target} on WhatsApp.",
        "hi": "{target} को WhatsApp पर भेज रहा हूँ।",
        "hinglish": "{target} ko WhatsApp pe bhej raha hoon.",
    },
    INTENT_SEARCH_WEB: {
        "en": "Searching Google for {target}.",
        "hi": "Google पर {target} खोज रहा हूँ।",
        "hinglish": "Google pe {target} search kar raha hoon.",
    },
    INTENT_PLAY_MEDIA: {
        "en": "Playing.",
        "hi": "चला रहा हूँ।",
        "hinglish": "Play kar raha hoon.",
    },
    INTENT_PAUSE_MEDIA: {
        "en": "Paused.",
        "hi": "पॉज़ किया।",
        "hinglish": "Pause kar diya.",
    },
    INTENT_STOP_MEDIA: {
        "en": "Stopped.",
        "hi": "बंद किया।",
        "hinglish": "Band kar diya.",
    },
    INTENT_NEXT_TRACK: {
        "en": "Next track.",
        "hi": "अगला गाना।",
        "hinglish": "Next gaana.",
    },
    INTENT_PREV_TRACK: {
        "en": "Previous track.",
        "hi": "पिछला गाना।",
        "hinglish": "Previous gaana.",
    },
    INTENT_INCREASE_VOLUME: {
        "en": "Volume increased.",
        "hi": "वॉल्यूम बढ़ा रहा हूँ।",
        "hinglish": "Volume badha raha hoon.",
    },
    INTENT_DECREASE_VOLUME: {
        "en": "Volume decreased.",
        "hi": "वॉल्यूम कम कर रहा हूँ।",
        "hinglish": "Volume kam kar raha hoon.",
    },
    INTENT_MUTE: {
        "en": "Muted.",
        "hi": "म्यूट कर दिया।",
        "hinglish": "Mute kar diya.",
    },
    INTENT_UNMUTE: {
        "en": "Unmuted.",
        "hi": "अनम्यूट कर दिया।",
        "hinglish": "Unmute kar diya.",
    },
    INTENT_TAKE_SCREENSHOT: {
        "en": "Taking a screenshot.",
        "hi": "स्क्रीनशॉट ले रहा हूँ।",
        "hinglish": "Screenshot le raha hoon.",
    },
    INTENT_CREATE_FOLDER: {
        "en": "Creating folder.",
        "hi": "फ़ोल्डर बना रहा हूँ।",
        "hinglish": "Folder bana raha hoon.",
    },
    INTENT_SHUTDOWN: {
        "en": "Shutdown will close your current session. Should I continue?",
        "hi": "कंप्यूटर बंद हो जाएगा। क्या मैं जारी रखूँ?",
        "hinglish": "Computer shutdown ho jayega. Continue karoon?",
    },
    INTENT_RESTART: {
        "en": "Restart will close your current session. Should I continue?",
        "hi": "कंप्यूटर रीस्टार्ट होगा। क्या मैं जारी रखूँ?",
        "hinglish": "Computer restart hoga. Continue karoon?",
    },
    INTENT_SLEEP: {
        "en": "This will put the computer to sleep. Should I continue?",
        "hi": "कंप्यूटर स्लीप में जाएगा। जारी रखूँ?",
        "hinglish": "Computer sleep mode mein jayega. Continue karoon?",
    },
    INTENT_LOCK_PC: {
        "en": "Locking the computer.",
        "hi": "कंप्यूटर लॉक कर रहा हूँ।",
        "hinglish": "Computer lock kar raha hoon.",
    },
    INTENT_GET_TIME: {
        "en": "",  # filled from tool
        "hi": "",
        "hinglish": "",
    },
}

_ERROR: dict[str, dict[str, str]] = {
    "not_caught": {
        "en": "Sorry, I didn't catch that.",
        "hi": "माफ़ कीजिए, मैं सुन नहीं पाया।",
        "hinglish": "Sorry, main sun nahi paya.",
    },
    "not_understood": {
        "en": "Sorry, I didn't understand that.",
        "hi": "माफ़ कीजिए, समझ नहीं आया।",
        "hinglish": "Sorry, samajh nahi aaya.",
    },
    "app_not_found": {
        "en": "I couldn't find that application.",
        "hi": "वह ऐप नहीं मिला।",
        "hinglish": "Woh app nahi mila.",
    },
}


def _lang_key(language: Language | str) -> str:
    if isinstance(language, Language):
        return language.value
    val = str(language).lower()
    if val in ("en", "english"):
        return "en"
    if val in ("hi", "hindi"):
        return "hi"
    if val in ("hinglish",):
        return "hinglish"
    return "en"


def format_response(
    intent: str,
    language: Language | str = Language.ENGLISH,
    target: str = "",
    fallback: str = "",
) -> str:
    key = _lang_key(language)
    templates = _TEMPLATES.get(intent)
    if not templates:
        return fallback
    text = templates.get(key) or templates.get("en") or fallback
    display = (target or "").replace("_", " ").strip()
    if display:
        # Title-case latin app names; leave Devanagari as-is
        if display.isascii():
            display = display.title()
        text = text.replace("{target}", display)
    else:
        text = text.replace("{target}", "").replace("  ", " ").strip()
    return text or fallback


def error_response(kind: str, language: Language | str = Language.ENGLISH) -> str:
    key = _lang_key(language)
    entry = _ERROR.get(kind, _ERROR["not_understood"])
    return entry.get(key) or entry["en"]
