"""Hindi / Hinglish / English intent normalization and pattern parsing.

Pipeline:
  raw text → strip wake word → detect language → normalize verbs →
  pattern intent OR phrase match → structured command
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.brain.language import Language, detect_language

# ---------------------------------------------------------------------------
# Canonical intents (map to tool registry actions)
# ---------------------------------------------------------------------------

INTENT_OPEN_APP = "OPEN_APP"
INTENT_CLOSE_APP = "CLOSE_APP"
INTENT_OPEN_WEBSITE = "OPEN_WEBSITE"
INTENT_SEARCH_WEB = "SEARCH_WEB"
INTENT_PLAY_MEDIA = "PLAY_MEDIA"
INTENT_PAUSE_MEDIA = "PAUSE_MEDIA"
INTENT_STOP_MEDIA = "STOP_MEDIA"
INTENT_NEXT_TRACK = "NEXT_TRACK"
INTENT_PREV_TRACK = "PREV_TRACK"
INTENT_INCREASE_VOLUME = "INCREASE_VOLUME"
INTENT_DECREASE_VOLUME = "DECREASE_VOLUME"
INTENT_MUTE = "MUTE"
INTENT_UNMUTE = "UNMUTE"
INTENT_TAKE_SCREENSHOT = "TAKE_SCREENSHOT"
INTENT_CREATE_FOLDER = "CREATE_FOLDER"
INTENT_SHUTDOWN = "SHUTDOWN"
INTENT_RESTART = "RESTART"
INTENT_SLEEP = "SLEEP"
INTENT_LOCK_PC = "LOCK_PC"
INTENT_GET_TIME = "GET_TIME"
INTENT_OPEN_FOLDER = "OPEN_FOLDER"
INTENT_OPEN_WHATSAPP = "OPEN_WHATSAPP"
INTENT_SEND_WHATSAPP = "SEND_WHATSAPP"
INTENT_UNKNOWN = "UNKNOWN"

# App / site aliases (latin + common misspellings + Devanagari)
APP_ALIASES: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "krom": "chrome",
    "क्रोम": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "firefox": "firefox",
    "notepad": "notepad",
    "नोटपैड": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "कैलकुलेटर": "calculator",
    "spotify": "spotify",
    "discord": "discord",
    "vscode": "vscode",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "explorer": "explorer",
    "file explorer": "explorer",
    "terminal": "terminal",
    "cmd": "terminal",
    "powershell": "terminal",
    "browser": "chrome",
    "ब्राउज़र": "chrome",
}

WEBSITE_ALIASES: dict[str, str] = {
    "youtube": "youtube",
    "yt": "youtube",
    "यूट्यूब": "youtube",
    "यू ट्यूब": "youtube",
    "google": "google",
    "गूगल": "google",
    "github": "github",
    "git hub": "github",
    "git": "github",
    "whatsapp": "whatsapp",
    "whats app": "whatsapp",
    "whatsapp web": "whatsapp",
    "व्हाट्सएप": "whatsapp",
}

FOLDER_ALIASES: dict[str, str] = {
    "downloads": "downloads",
    "download": "downloads",
    "documents": "documents",
    "docs": "documents",
    "desktop": "desktop",
}

# Verb phrase → English canonical fragment (longest first matching)
# Note: avoid trailing \\b after Devanagari consonants — matras are not \\w,
# so \\bखोल\\b incorrectly matches inside खोलो.
_DEV_BOUND_L = r"(?<![\u0900-\u097F])"
_DEV_BOUND_R = r"(?![\u0900-\u097F])"

_VERB_REPLACEMENTS: list[tuple[str, str]] = [
    # open
    (r"\bkhol\s+do\b", "open"),
    (r"\bkhol\s+de\b", "open"),
    (r"\bkholdo\b", "open"),
    (r"\bkholde\b", "open"),
    (r"\bkhol\s+dena\b", "open"),
    (r"\bkholna\b", "open"),
    (r"\bkholo\b", "open"),
    (r"\bkhol\b", "open"),
    (r"\bopen\s+kar\s+do\b", "open"),
    (r"\bopen\s+kar\s+de\b", "open"),
    (r"\bopen\s+kardo\b", "open"),
    (r"\bopen\s+karde\b", "open"),
    (r"\bopen\s+karo\b", "open"),
    (r"\bopen\s+kar\b", "open"),
    (r"\blaunch\s+karo\b", "open"),
    (r"\blaunch\s+kar\s+do\b", "open"),
    (r"\bstart\s+karo\b", "open"),
    (r"\bstart\s+kar\s+do\b", "open"),
    (_DEV_BOUND_L + r"खोल\s*दो" + _DEV_BOUND_R, "open"),
    (_DEV_BOUND_L + r"खोल\s*दे" + _DEV_BOUND_R, "open"),
    (_DEV_BOUND_L + r"खोलो" + _DEV_BOUND_R, "open"),
    (_DEV_BOUND_L + r"खोलना" + _DEV_BOUND_R, "open"),
    (_DEV_BOUND_L + r"खोलें" + _DEV_BOUND_R, "open"),
    (_DEV_BOUND_L + r"खोल" + _DEV_BOUND_R, "open"),
    # play / start media
    (r"\bchala\s+do\b", "play"),
    (r"\bchala\s+de\b", "play"),
    (r"\bchalao\b", "play"),
    (r"\bchalu\s+karo\b", "play"),
    (r"\bplay\s+karo\b", "play"),
    (r"\bplay\s+kar\s+do\b", "play"),
    (_DEV_BOUND_L + r"चलाओ" + _DEV_BOUND_R, "play"),
    (_DEV_BOUND_L + r"चला\s*दो" + _DEV_BOUND_R, "play"),
    # close
    (r"\bbandh?\s+kar\s+do\b", "close"),
    (r"\bbandh?\s+kar\s+de\b", "close"),
    (r"\bbandh?\s+karo\b", "close"),
    (r"\bbandh?\s+kardo\b", "close"),
    (r"\bclose\s+karo\b", "close"),
    (r"\bclose\s+kar\s+do\b", "close"),
    (_DEV_BOUND_L + r"बंद\s*कर\s*दो" + _DEV_BOUND_R, "close"),
    (_DEV_BOUND_L + r"बंद\s*करो" + _DEV_BOUND_R, "close"),
    (_DEV_BOUND_L + r"बंद" + _DEV_BOUND_R, "close"),
    # volume up / down — match बढ़ा / बढ़ाओ with flexible nukta forms
    (r"\bbadha\s+do\b", "increase"),
    (r"\bbadha\s+de\b", "increase"),
    (r"\bbadhao\b", "increase"),
    (r"\bbadao\b", "increase"),
    (_DEV_BOUND_L + r"बढ.?ा\s*दो" + _DEV_BOUND_R, "increase"),
    (_DEV_BOUND_L + r"बढ.?ाओ" + _DEV_BOUND_R, "increase"),
    (_DEV_BOUND_L + r"बढ़ा\s*दो" + _DEV_BOUND_R, "increase"),
    (_DEV_BOUND_L + r"बढ़ाओ" + _DEV_BOUND_R, "increase"),
    (r"\bkam\s+karo\b", "decrease"),
    (r"\bkam\s+kar\s+do\b", "decrease"),
    (r"\bkam\s+kar\s+de\b", "decrease"),
    (r"\bghatao\b", "decrease"),
    (_DEV_BOUND_L + r"कम\s*करो" + _DEV_BOUND_R, "decrease"),
    (_DEV_BOUND_L + r"कम\s*कर\s*दो" + _DEV_BOUND_R, "decrease"),
    # search
    (r"\bsearch\s+karo\b", "search"),
    (r"\bsearch\s+kar\s+do\b", "search"),
    (r"\bsearch\s+kar\s+de\b", "search"),
    (r"\bdhoondh?o\b", "search"),
    (r"\bdhundh?o\b", "search"),
    (_DEV_BOUND_L + r"ढूंढो" + _DEV_BOUND_R, "search"),
    (_DEV_BOUND_L + r"खोजो" + _DEV_BOUND_R, "search"),
    # show / tell
    (r"\bdikhao\b", "show"),
    (r"\bdikha\s+do\b", "show"),
    (r"\bbatao\b", "tell"),
    (r"\bbata\s+do\b", "tell"),
    (_DEV_BOUND_L + r"दिखाओ" + _DEV_BOUND_R, "show"),
    (_DEV_BOUND_L + r"बताओ" + _DEV_BOUND_R, "tell"),
    # create
    (r"\bbanao\b", "create"),
    (r"\bbana\s+do\b", "create"),
    (r"\bcreate\s+karo\b", "create"),
    (_DEV_BOUND_L + r"बनाओ" + _DEV_BOUND_R, "create"),
    (_DEV_BOUND_L + r"बना\s*दो" + _DEV_BOUND_R, "create"),
    # mute helpers
    (r"\bmute\s+karo\b", "mute"),
    (r"\bunmute\s+karo\b", "unmute"),
    # particles / fillers often left after verb strip
    (r"\bko\b", " "),
    (_DEV_BOUND_L + r"को" + _DEV_BOUND_R, " "),
    (r"\bplease\b", " "),
    (r"\bpls\b", " "),
    (r"\bkr\s+do\b", " "),
    (_DEV_BOUND_L + r"कर\s*दो" + _DEV_BOUND_R, " "),
    (_DEV_BOUND_L + r"करो" + _DEV_BOUND_R, " "),
]

# Compiled once
_VERB_PATTERNS = [(re.compile(p, re.IGNORECASE), repl) for p, repl in _VERB_REPLACEMENTS]

_WAKE_PREFIXES = (
    "hey jarvis", "ok jarvis", "hi jarvis", "jarvis",
)

# Noise words to drop from targets
_FILLER = frozenset({
    "the", "a", "an", "my", "please", "pls", "jarvis",
    "mera", "meri", "mere", "ek", "do", "abhi", "jaldi",
    "मेरा", "मेरी", "एक",
})


@dataclass
class ParsedIntent:
    intent: str
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    language: Language = Language.ENGLISH
    normalized: str = ""
    confidence: float = 0.0
    raw: str = ""

    def to_tool(self) -> tuple[str, dict[str, Any]] | None:
        """Map canonical intent → (tool_name, arguments)."""
        mapping = _INTENT_TOOL_MAP.get(self.intent)
        if mapping is None:
            return None
        tool, builder = mapping
        return tool, builder(self)


def _tool_open_app(p: ParsedIntent) -> dict[str, Any]:
    return {"application": p.target or p.parameters.get("application", "")}


def _tool_close_app(p: ParsedIntent) -> dict[str, Any]:
    return {"application": p.target or p.parameters.get("application", "")}


def _tool_open_website(p: ParsedIntent) -> dict[str, Any]:
    site = (p.target or "youtube").lower()
    if site == "youtube":
        return {}  # open_youtube takes no args — handled specially
    if site == "google":
        return {"url": "https://www.google.com"}
    return {"url": f"https://{site}.com"}


def _tool_search(p: ParsedIntent) -> dict[str, Any]:
    return {"query": p.parameters.get("query") or p.target}


def _tool_volume(action: str):
    def _inner(_p: ParsedIntent) -> dict[str, Any]:
        return {"action": action}
    return _inner


def _tool_media(action: str):
    def _inner(_p: ParsedIntent) -> dict[str, Any]:
        return {"action": action}
    return _inner


def _tool_power(action: str):
    def _inner(_p: ParsedIntent) -> dict[str, Any]:
        return {"action": action}
    return _inner


def _tool_empty(_p: ParsedIntent) -> dict[str, Any]:
    return {}


def _tool_create_folder(p: ParsedIntent) -> dict[str, Any]:
    name = p.parameters.get("name") or p.target or "New Folder"
    # Default to Desktop for voice "ek folder banao"
    import os
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    path = os.path.join(desktop, name)
    return {"path": path}


def _tool_open_folder(p: ParsedIntent) -> dict[str, Any]:
    return {"path": p.target or p.parameters.get("path", "")}


def _tool_whatsapp_send(p: ParsedIntent) -> dict[str, Any]:
    return {
        "contact": p.target or p.parameters.get("contact", ""),
        "message": p.parameters.get("message", ""),
        "phone": p.parameters.get("phone", ""),
    }


_INTENT_TOOL_MAP: dict[str, tuple[str, Any]] = {
    INTENT_OPEN_APP: ("open_application", _tool_open_app),
    INTENT_CLOSE_APP: ("close_application", _tool_close_app),
    INTENT_OPEN_WEBSITE: ("open_youtube", _tool_open_website),  # overridden below for non-yt
    INTENT_SEARCH_WEB: ("google_search", _tool_search),
    INTENT_PLAY_MEDIA: ("media_control", _tool_media("play")),
    INTENT_PAUSE_MEDIA: ("media_control", _tool_media("pause")),
    INTENT_STOP_MEDIA: ("media_control", _tool_media("stop")),
    INTENT_NEXT_TRACK: ("media_control", _tool_media("next")),
    INTENT_PREV_TRACK: ("media_control", _tool_media("previous")),
    INTENT_INCREASE_VOLUME: ("volume_control", _tool_volume("up")),
    INTENT_DECREASE_VOLUME: ("volume_control", _tool_volume("down")),
    INTENT_MUTE: ("volume_control", _tool_volume("mute")),
    INTENT_UNMUTE: ("volume_control", _tool_volume("unmute")),
    INTENT_TAKE_SCREENSHOT: ("take_screenshot", _tool_empty),
    INTENT_CREATE_FOLDER: ("create_folder", _tool_create_folder),
    INTENT_SHUTDOWN: ("system_power", _tool_power("shutdown")),
    INTENT_RESTART: ("system_power", _tool_power("restart")),
    INTENT_SLEEP: ("system_power", _tool_power("sleep")),
    INTENT_LOCK_PC: ("lock_computer", _tool_empty),
    INTENT_GET_TIME: ("get_time", _tool_empty),
    INTENT_OPEN_FOLDER: ("open_folder", _tool_open_folder),
    INTENT_OPEN_WHATSAPP: ("open_whatsapp", _tool_empty),
    INTENT_SEND_WHATSAPP: ("send_whatsapp_message", _tool_whatsapp_send),
}


def strip_wake_word(text: str, jarvis_name: str = "jarvis") -> str:
    text = text.lower().strip()
    text = text.replace("'", "'").replace("'", "'")
    # Keep Devanagari; strip other punctuation
    text = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    prefixes = list(_WAKE_PREFIXES) + [jarvis_name.lower()]
    for prefix in sorted(set(prefixes), key=len, reverse=True):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix) + 1 :].strip()
    return text


def normalize_verbs(text: str) -> str:
    """Replace Hindi/Hinglish verb phrases with English canonical verbs."""
    result = text
    for pattern, repl in _VERB_PATTERNS:
        result = pattern.sub(repl, result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _resolve_app(name: str) -> str | None:
    n = name.lower().strip()
    n = re.sub(r"\s+", " ", n)
    if n in APP_ALIASES:
        return APP_ALIASES[n]
    # try without fillers
    parts = [p for p in n.split() if p not in _FILLER]
    cleaned = " ".join(parts)
    if cleaned in APP_ALIASES:
        return APP_ALIASES[cleaned]
    for alias, canonical in APP_ALIASES.items():
        if alias in cleaned or cleaned in alias:
            return canonical
    return cleaned if cleaned else None


def _resolve_folder(name: str) -> str | None:
    n = name.lower().strip()
    n = re.sub(r"^my\s+", "", n)
    n = re.sub(r"\s+folder$", "", n)
    if n in FOLDER_ALIASES:
        return FOLDER_ALIASES[n]
    try:
        from app.tools.app_catalog import folder_key
        return folder_key(n)
    except Exception:
        return None


def _resolve_site(name: str) -> str | None:
    n = name.lower().strip()
    if n in WEBSITE_ALIASES:
        return WEBSITE_ALIASES[n]
    for alias, canonical in WEBSITE_ALIASES.items():
        if alias in n:
            return canonical
    try:
        from app.tools.app_catalog import website_url
        if website_url(n):
            return n
    except Exception:
        pass
    return None


def _clean_target(text: str) -> str:
    parts = [p for p in text.lower().split() if p not in _FILLER]
    return " ".join(parts).strip()


_WA_TOKEN = r"(?:whatsapp|whats\s*app|व्हाट्सएप)"


def _match_whatsapp(t: str, language: Language, raw: str) -> ParsedIntent | None:
    """Open WhatsApp Web or send a message to a named contact."""
    if not re.search(_WA_TOKEN, t, re.I):
        return None

    send_patterns = [
        re.compile(
            r"send\s+(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?to\s+"
            r"(?P<contact>.+?)\s+(?:on\s+whatsapp\s+)?(?:saying|that|says|:)\s+(?P<msg>.+)$",
            re.I,
        ),
        re.compile(
            r"send\s+(?:a\s+)?message\s+to\s+(?P<contact>.+?)\s+on\s+whatsapp"
            r"(?:\s+(?:saying|that|:)\s+(?P<msg>.+))?$",
            re.I,
        ),
        re.compile(
            r"message\s+(?P<contact>.+?)\s+on\s+whatsapp"
            r"(?:\s+(?:saying|that|:)\s+(?P<msg>.+))?$",
            re.I,
        ),
        re.compile(
            r"whatsapp\s+(?P<contact>.+?)\s+(?:saying|that|says|:)\s+(?P<msg>.+)$",
            re.I,
        ),
        re.compile(
            r"send\s+(?P<msg>.+?)\s+to\s+(?P<contact>.+?)\s+(?:on|via|using)\s+whatsapp\s*$",
            re.I,
        ),
        re.compile(
            r"(?:whatsapp|message)\s+(?:pe\s+)?(?P<contact>.+?)\s+ko\s+"
            r"(?:message\s+)?(?:bhejo|bhej\s+do|karo)\s+(?P<msg>.+)$",
            re.I,
        ),
        re.compile(
            r"(?P<contact>.+?)\s+ko\s+whatsapp\s+(?:pe\s+)?(?:message\s+)?"
            r"(?:bhejo|bhej\s+do|karo)\s+(?P<msg>.+)$",
            re.I,
        ),
        re.compile(
            r"whatsapp\s+(?:pe\s+)?(?:message\s+)?(?:bhejo|karo)\s+"
            r"(?P<contact>.+?)\s+(?:ko\s+)?(?P<msg>.+)$",
            re.I,
        ),
    ]
    for pat in send_patterns:
        m = pat.search(t)
        if not m:
            continue
        contact = _clean_whatsapp_contact(m.group("contact"))
        msg = (m.groupdict().get("msg") or "").strip()
        msg = re.sub(r"^(saying|that|says|:)\s+", "", msg, flags=re.I).strip()
        if contact:
            return ParsedIntent(
                INTENT_SEND_WHATSAPP,
                target=contact,
                parameters={"contact": contact, "message": msg},
                language=language,
                normalized=t,
                confidence=0.95,
                raw=raw,
            )

    chat_only = re.search(
        r"(?:open\s+)?(?:whatsapp\s+)?chat\s+with\s+(?P<contact>.+)$",
        t,
        re.I,
    )
    if chat_only:
        contact = _clean_whatsapp_contact(chat_only.group("contact"))
        if contact:
            return ParsedIntent(
                INTENT_SEND_WHATSAPP,
                target=contact,
                parameters={"contact": contact, "message": ""},
                language=language,
                normalized=t,
                confidence=0.9,
                raw=raw,
            )

    # "whatsapp mom" with no saying-clause — open that chat
    bare = re.match(rf"^{_WA_TOKEN}\s+(?P<contact>.+)$", t, re.I)
    if bare:
        contact = _clean_whatsapp_contact(bare.group("contact"))
        skip = {"web", "app", "please", "kholo", "open", "launch", "start"}
        if contact and contact not in skip and not re.search(
            r"\b(open|launch|start|kholo)\b", t, re.I
        ):
            return ParsedIntent(
                INTENT_SEND_WHATSAPP,
                target=contact,
                parameters={"contact": contact, "message": ""},
                language=language,
                normalized=t,
                confidence=0.88,
                raw=raw,
            )

    return ParsedIntent(
        INTENT_OPEN_WHATSAPP,
        target="whatsapp",
        language=language,
        normalized=t,
        confidence=0.95,
        raw=raw,
    )


def _clean_whatsapp_contact(name: str) -> str:
    n = (name or "").strip()
    n = re.sub(_WA_TOKEN, " ", n, flags=re.I)
    n = re.sub(r"\b(on|via|using|please|ko|pe|par|a|the|chat|message|web)\b", " ", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" .,-")
    return n


# ---------------------------------------------------------------------------
# Pattern-based intent extraction (works on raw + normalized forms)
# ---------------------------------------------------------------------------

def _match_patterns(text: str, language: Language) -> ParsedIntent | None:
    t = text.strip()
    if not t:
        return None

    wa = _match_whatsapp(t, language, text)
    if wa is not None:
        return wa

    # --- Volume ---
    if re.search(r"\b(volume|awaz|aawaaz|sound|आवाज|आवाज़|वॉल्यूम)\b", t, re.I) or re.search(
        r"(आवाज|आवाज़|वॉल्यूम)", t
    ):
        if re.search(r"\b(increase|up|raise|badha|badhao|zyada|jyada)\b", t, re.I) or re.search(
            r"बढ.?ा|बढ़ा", t
        ):
            return ParsedIntent(INTENT_INCREASE_VOLUME, language=language, normalized=t, confidence=0.95, raw=text)
        if re.search(r"\b(decrease|down|lower|kam|ghata)\b", t, re.I) or re.search(r"कम", t):
            return ParsedIntent(INTENT_DECREASE_VOLUME, language=language, normalized=t, confidence=0.95, raw=text)
        if re.search(r"\b(unmute)\b", t, re.I):
            return ParsedIntent(INTENT_UNMUTE, language=language, normalized=t, confidence=0.95, raw=text)
        if re.search(r"\b(mute|silence)\b", t, re.I):
            return ParsedIntent(INTENT_MUTE, language=language, normalized=t, confidence=0.95, raw=text)

    if re.search(r"\b(mute|unmute)\b", t, re.I) and not re.search(r"\b(volume|awaz)\b", t, re.I):
        if "unmute" in t:
            return ParsedIntent(INTENT_UNMUTE, language=language, normalized=t, confidence=0.9, raw=text)
        return ParsedIntent(INTENT_MUTE, language=language, normalized=t, confidence=0.9, raw=text)

    # --- Power (high confidence only) ---
    shutdown_pat = re.compile(
        r"\b((shut\s*down|shutdown|turn\s*off).*(computer|pc|laptop|system)"
        r"|(computer|pc|laptop|system).*(shut\s*down|shutdown|turn\s*off)"
        r"|mera\s+(laptop|computer|pc).*(shutdown|band|close)"
        r"|(laptop|computer|pc)\s*(shutdown|band)"
        r"|कंप्यूटर\s*बंद|लैपटॉप\s*बंद|shutdown\s*karo)\b",
        re.I,
    )
    if shutdown_pat.search(t) or t in ("shutdown", "shut down", "pc band karo", "computer band karo",
                                         "laptop band karo", "computer shutdown karo",
                                         "mera laptop shutdown karo"):
        return ParsedIntent(INTENT_SHUTDOWN, language=language, normalized=t, confidence=0.92, raw=text)

    if re.search(r"\b(restart|reboot).*(computer|pc|laptop)?|(computer|pc)\s*restart\b", t, re.I):
        return ParsedIntent(INTENT_RESTART, language=language, normalized=t, confidence=0.92, raw=text)

    if re.search(r"\b(sleep|hibernate)\b", t, re.I) and re.search(r"\b(computer|pc|laptop|system)?\b", t, re.I):
        if t.strip() in ("sleep",) or "sleep" in t:
            return ParsedIntent(INTENT_SLEEP, language=language, normalized=t, confidence=0.85, raw=text)

    # --- Lock ---
    if re.search(r"\b(lock).*(pc|computer|screen|laptop)|(pc|computer)\s*lock\b", t, re.I):
        return ParsedIntent(INTENT_LOCK_PC, language=language, normalized=t, confidence=0.95, raw=text)

    # --- Screenshot ---
    if re.search(r"\b(screenshot|screen\s*capture|screenshot\s*lo)\b", t, re.I):
        return ParsedIntent(INTENT_TAKE_SCREENSHOT, language=language, normalized=t, confidence=0.95, raw=text)

    # --- Time ---
    if re.search(r"\b(what\s*time|current\s*time|time\s*batao|kitna\s*time|tell\s*me\s*the\s*time)\b", t, re.I):
        return ParsedIntent(INTENT_GET_TIME, language=language, normalized=t, confidence=0.95, raw=text)

    # --- Media play/pause (without specific app) ---
    if re.search(r"\b(music|gaana|gana|song|media|गाना)\b", t, re.I):
        if re.search(r"\b(play|chala|resume)\b", t, re.I):
            return ParsedIntent(INTENT_PLAY_MEDIA, language=language, normalized=t, confidence=0.9, raw=text)
        if re.search(r"\b(pause)\b", t, re.I):
            return ParsedIntent(INTENT_PAUSE_MEDIA, language=language, normalized=t, confidence=0.9, raw=text)
        if re.search(r"\b(stop|band)\b", t, re.I):
            return ParsedIntent(INTENT_STOP_MEDIA, language=language, normalized=t, confidence=0.9, raw=text)

    if re.search(r"\b(next\s*(song|track|gaana)|aglai?\s*gaana)\b", t, re.I):
        return ParsedIntent(INTENT_NEXT_TRACK, language=language, normalized=t, confidence=0.9, raw=text)
    if re.search(r"\b(previous\s*(song|track)|pichla\s*gaana|prev\s*song)\b", t, re.I):
        return ParsedIntent(INTENT_PREV_TRACK, language=language, normalized=t, confidence=0.9, raw=text)

    # --- Create folder ---
    if re.search(r"\b(folder|directory|डायरेक्टरी|फोल्डर)\b", t, re.I) and re.search(
        r"\b(create|make|new|bana|mkdir)\b", t, re.I
    ):
        name_m = re.search(r"(?:called|named|naam)\s+(\w+)", t, re.I)
        name = name_m.group(1) if name_m else "New Folder"
        return ParsedIntent(
            INTENT_CREATE_FOLDER, target=name, parameters={"name": name},
            language=language, normalized=t, confidence=0.9, raw=text,
        )

    # --- Google / web search ---
    # "google pe/par/mein X search" | "search google for X" | "google par search karo X"
    search_patterns = [
        re.compile(
            r"(?:google|गूगल)\s*(?:pe|par|mein|me|on|पर|पे|में)?\s*"
            r"(?:search\s*(?:karo|kar\s*do|for)?\s*)?(?P<q>.+?)$",
            re.I,
        ),
        re.compile(
            r"search\s+(?:karo\s+)?(?:google\s+(?:pe|par|for)\s+)?(?P<q>.+)$",
            re.I,
        ),
        re.compile(
            r"(?:google|गूगल)\s+(?:search\s+)?(?:for\s+)?(?P<q>.+)$",
            re.I,
        ),
        re.compile(
            r"(?P<q>.+?)\s+(?:google\s+)?(?:pe|par)\s+search$",
            re.I,
        ),
    ]
    if re.search(r"\b(search|google|dhoondo|dhundo|गूगल|खोज)\b", t, re.I):
        # Avoid treating "open google" as search
        if not re.search(r"\b(open|launch|start)\s+google\s*$", t, re.I):
            for pat in search_patterns:
                m = pat.search(t)
                if m:
                    q = _clean_target(m.group("q"))
                    # Strip leftover search verbs
                    q = re.sub(r"\b(search|karo|for|pe|par|mein)\b", " ", q, flags=re.I)
                    q = re.sub(r"\s+", " ", q).strip()
                    if q and q not in ("google", "youtube", "web"):
                        return ParsedIntent(
                            INTENT_SEARCH_WEB, target=q, parameters={"query": q},
                            language=language, normalized=t, confidence=0.9, raw=text,
                        )

    # --- YouTube play/open ---
    if re.search(r"\b(youtube|yt|यूट्यूब)\b", t, re.I):
        # "youtube par music chalao" → play media OR open youtube
        if re.search(r"\b(music|gaana|song)\b", t, re.I) and re.search(r"\b(play|chala)\b", t, re.I):
            return ParsedIntent(INTENT_PLAY_MEDIA, language=language, normalized=t, confidence=0.85, raw=text)
        if re.search(r"\b(open|play|launch|start|chala)\b", t, re.I) or re.search(
            r"(youtube|yt|यूट्यूब)\s*$", t, re.I
        ):
            # "chrome mein youtube open" handled below; plain youtube → website
            if not re.search(r"\b(chrome|firefox|edge|browser)\b", t, re.I):
                return ParsedIntent(
                    INTENT_OPEN_WEBSITE, target="youtube",
                    language=language, normalized=t, confidence=0.95, raw=text,
                )

    # --- "X mein/par YouTube open" → open youtube (browser) ---
    if re.search(r"\b(chrome|browser|firefox|edge).*(youtube|yt)|(youtube|yt).*(chrome|browser)\b", t, re.I):
        return ParsedIntent(
            INTENT_OPEN_WEBSITE, target="youtube",
            language=language, normalized=t, confidence=0.9, raw=text,
        )

    # --- Open / close app patterns ---
    # Normalized form: "open chrome" | raw hinglish already verb-normalized
    m = re.match(r"^(?:open|launch|start)\s+(.+)$", t, re.I)
    if m:
        target_raw = _clean_target(m.group(1))
        folder = _resolve_folder(target_raw)
        if folder:
            return ParsedIntent(
                INTENT_OPEN_FOLDER, target=folder, parameters={"path": folder},
                language=language, normalized=t, confidence=0.95, raw=text,
            )
        site = _resolve_site(target_raw)
        if site:
            return ParsedIntent(
                INTENT_OPEN_WEBSITE, target=site,
                language=language, normalized=t, confidence=0.95, raw=text,
            )
        app = _resolve_app(target_raw)
        if app:
            return ParsedIntent(
                INTENT_OPEN_APP, target=app, parameters={"application": app},
                language=language, normalized=t, confidence=0.95, raw=text,
            )

    m = re.match(r"^(.+?)\s+(?:open|launch|start)$", t, re.I)
    if m:
        target_raw = _clean_target(m.group(1))
        site = _resolve_site(target_raw)
        if site:
            return ParsedIntent(
                INTENT_OPEN_WEBSITE, target=site,
                language=language, normalized=t, confidence=0.9, raw=text,
            )
        app = _resolve_app(target_raw)
        if app:
            return ParsedIntent(
                INTENT_OPEN_APP, target=app, parameters={"application": app},
                language=language, normalized=t, confidence=0.9, raw=text,
            )

    m = re.match(r"^(?:close|quit|exit)\s+(.+)$", t, re.I)
    if m:
        app = _resolve_app(_clean_target(m.group(1)))
        if app:
            return ParsedIntent(
                INTENT_CLOSE_APP, target=app, parameters={"application": app},
                language=language, normalized=t, confidence=0.9, raw=text,
            )

    # Bare app name alone is too ambiguous — skip
    return None


def parse_intent(text: str, jarvis_name: str = "jarvis") -> ParsedIntent:
    """Full pipeline: detect language, normalize, extract structured intent."""
    raw = text.strip()
    stripped = strip_wake_word(raw, jarvis_name)
    language = detect_language(stripped or raw)
    normalized = normalize_verbs(stripped)
    # Also normalize Devanagari app names lightly via alias resolution later

    # Try patterns on normalized text first, then on stripped original
    for candidate in (normalized, stripped):
        parsed = _match_patterns(candidate, language)
        if parsed is not None:
            parsed.language = language
            parsed.normalized = normalized
            parsed.raw = raw
            return parsed

    return ParsedIntent(
        intent=INTENT_UNKNOWN,
        language=language,
        normalized=normalized,
        confidence=0.0,
        raw=raw,
    )


def intent_to_tool_call(parsed: ParsedIntent) -> tuple[str, dict[str, Any]] | None:
    """Resolve ParsedIntent to registry tool + arguments."""
    if parsed.intent == INTENT_UNKNOWN:
        return None

    if parsed.intent == INTENT_OPEN_WEBSITE:
        site = (parsed.target or "").lower()
        if site == "youtube":
            return "open_youtube", {}
        if site == "whatsapp":
            return "open_whatsapp", {}
        try:
            from app.tools.app_catalog import website_url
            url = website_url(site)
            if url:
                return "open_url", {"url": url}
        except Exception:
            pass
        if site == "google":
            return "open_url", {"url": "https://www.google.com"}
        return "open_url", {"url": f"https://{site}.com"}

    return parsed.to_tool()
