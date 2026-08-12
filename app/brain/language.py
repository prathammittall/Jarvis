"""Lightweight language detection for English / Hindi / Hinglish."""

from __future__ import annotations

import re
from enum import Enum


class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"


# Devanagari block
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

# Common Hindi/Hinglish romanized command & function words
_HINGLISH_MARKERS = frozenset({
    "kholo", "khol", "kholna", "kholne", "kholunga", "kholen",
    "karo", "kar", "karna", "karne", "kar do", "kar de",
    "chalao", "chala", "chalu", "chalana",
    "band", "bandh", "bandho",
    "badhao", "badha", "badao",
    "kam", "ghatao", "ghata",
    "batao", "bata", "dikhao", "dikha",
    "dhoondo", "dhundo", "dhundho", "dhoondho",
    "banao", "bana", "banado",
    "pe", "par", "mein", "me", "ko", "se", "ka", "ki", "ke",
    "mera", "meri", "mere", "mujhe", "mujhse", "apka", "apna",
    "ek", "do", "abhi", "jaldi", "thoda", "zyada", "jyada",
    "gaana", "gana", "awaz", "aawaaz",
    "please",  # often glued onto hinglish; alone not enough
    "hai", "hain", "hoon", "hun", "raha", "rahi", "rahe",
    "karo", "kardo", "karde",
    "shutdown",  # english word often used in hinglish — scored only with others
})

# Strong markers that almost always mean Hinglish when paired with English nouns
_STRONG_HINGLISH = frozenset({
    "kholo", "khol", "kholna", "karo", "chalao", "chala", "band", "bandh",
    "badhao", "badha", "batao", "dikhao", "dhoondo", "dhundo", "banao",
    "awaz", "gaana", "gana", "mera", "meri", "mujhe", "abhi", "jaldi",
    "kardo", "karde", "kholde", "kholdo",
})

_DEVANAGARI_MARKERS = (
    "खोलो", "खोल", "करो", "चलाओ", "बंद", "बढ़ा", "बढ़ाओ", "कम",
    "बताओ", "दिखाओ", "ढूंढो", "बनाओ", "आवाज़", "गाना", "मेरा",
)


def _tokenize(text: str) -> list[str]:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)
    return [t for t in text.split() if t]


def detect_language(text: str) -> Language:
    """
    Classify utterance as ENGLISH, HINDI, or HINGLISH.

    Rules (fast, no network):
    - Significant Devanagari → HINDI (or HINGLISH if Latin app names dominate)
    - Roman Hindi verbs/particles with English nouns → HINGLISH
    - Otherwise → ENGLISH
    """
    if not text or not text.strip():
        return Language.ENGLISH

    raw = text.strip()
    tokens = _tokenize(raw)
    if not tokens:
        return Language.ENGLISH

    dev_chars = len(_DEVANAGARI.findall(raw))
    latin_chars = sum(1 for c in raw if "a" <= c.lower() <= "z")
    total_alpha = max(dev_chars + latin_chars, 1)

    has_devanagari = dev_chars > 0
    strong = sum(1 for t in tokens if t in _STRONG_HINGLISH)
    weak = sum(1 for t in tokens if t in _HINGLISH_MARKERS)
    # Devanagari marker substrings
    if any(m in raw for m in _DEVANAGARI_MARKERS):
        has_devanagari = True

    if has_devanagari:
        # Pure or mostly Devanagari → HINDI; mixed script with English nouns → still HINDI
        # if Devanagari is the instruction language
        if latin_chars > 0 and strong + weak > 0:
            # e.g. "Chrome खोलो" — treat as HINDI for TTS (Devanagari response)
            return Language.HINDI
        if latin_chars / total_alpha > 0.45 and weak == 0:
            return Language.HINGLISH
        return Language.HINDI

    if strong >= 1:
        return Language.HINGLISH
    if weak >= 2:
        return Language.HINGLISH

    # "open karo" style: English verb + karo already caught by strong
    # "google pe search" — pe is weak
    if "pe" in tokens or "par" in tokens or "mein" in tokens:
        if any(t in tokens for t in ("search", "open", "play", "close", "volume", "chrome",
                                       "youtube", "google", "notepad", "folder")):
            return Language.HINGLISH

    return Language.ENGLISH


def language_label(lang: Language) -> str:
    return {
        Language.ENGLISH: "ENGLISH",
        Language.HINDI: "HINDI",
        Language.HINGLISH: "HINGLISH",
    }[lang]
