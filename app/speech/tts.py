"""Local text-to-speech using Piper (English) with Windows SAPI Hindi fallback."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.brain.language import Language, detect_language
from app.config import PROJECT_ROOT, get_settings
from app.core.logger import get_logger

logger = get_logger("tts")

_voice = None
_voice_lock = threading.Lock()
_stop_event = threading.Event()
_speaking = False
_hindi_sapi_available: bool | None = None


def _find_piper_model(voice_name: str) -> Path | None:
    models_dir = get_settings().piper_model_dir
    candidates = [
        models_dir / f"{voice_name}.onnx",
        PROJECT_ROOT / "models" / "piper" / f"{voice_name}.onnx",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _download_piper_voice(voice_name: str) -> Path | None:
    """Download Piper voice model if missing."""
    models_dir = get_settings().piper_model_dir
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = models_dir / f"{voice_name}.onnx"
    json_path = models_dir / f"{voice_name}.onnx.json"

    if onnx_path.exists():
        return onnx_path

    # Known Piper voice download roots on HuggingFace
    voice_urls: dict[str, str] = {
        "en_US-lessac-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium",
        "hi_IN-pratham-medium": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium",
    }

    if voice_name in voice_urls:
        base_url = voice_urls[voice_name]
        urls = {
            onnx_path: f"{base_url}/{voice_name}.onnx",
            json_path: f"{base_url}/{voice_name}.onnx.json",
        }
    elif "lessac" in voice_name:
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
        urls = {
            onnx_path: f"{base_url}/en_US-lessac-medium.onnx",
            json_path: f"{base_url}/en_US-lessac-medium.onnx.json",
        }
    else:
        logger.warning("Unknown voice '%s', using fallback download for lessac", voice_name)
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
        urls = {
            onnx_path: f"{base_url}/en_US-lessac-medium.onnx",
            json_path: f"{base_url}/en_US-lessac-medium.onnx.json",
        }

    try:
        import urllib.request
        for path, url in urls.items():
            if not path.exists():
                logger.info("Downloading %s...", path.name)
                urllib.request.urlretrieve(url, path)
        return onnx_path
    except Exception as e:
        logger.error("Failed to download Piper voice: %s", e)
        return None


def get_piper_voice():
    global _voice
    with _voice_lock:
        if _voice is None:
            settings = get_settings()
            model_path = _find_piper_model(settings.tts_voice)
            if model_path is None:
                model_path = _download_piper_voice(settings.tts_voice)
            if model_path is None:
                raise RuntimeError(
                    "Piper voice model not found. Run: python scripts/download_models.py"
                )
            from piper.voice import PiperVoice
            _voice = PiperVoice.load(str(model_path))
            logger.info("Loaded Piper voice: %s", model_path.name)
        return _voice


def _has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text))


def _check_hindi_sapi() -> bool:
    global _hindi_sapi_available
    if _hindi_sapi_available is not None:
        return _hindi_sapi_available
    if sys.platform != "win32":
        _hindi_sapi_available = False
        return False
    try:
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "($s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Culture.Name }) -join ','"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        )
        cultures = (result.stdout or "").lower()
        _hindi_sapi_available = "hi-in" in cultures or "hi_" in cultures
        logger.info("Hindi SAPI voice available: %s", _hindi_sapi_available)
    except Exception as e:
        logger.warning("Could not probe Hindi SAPI voices: %s", e)
        _hindi_sapi_available = False
    return _hindi_sapi_available


def _sapi_speak(text: str, prefer_hindi: bool = False) -> bool:
    """Speak via Windows SAPI. Returns True on success."""
    if sys.platform != "win32":
        return False
    safe = text.replace('"', "'").replace("\n", " ")
    if not safe.strip():
        return False
    try:
        voice_select = ""
        if prefer_hindi:
            voice_select = (
                "$voices = $s.GetInstalledVoices(); "
                "foreach ($v in $voices) { "
                "  if ($v.VoiceInfo.Culture.Name -like 'hi*') { "
                "    $s.SelectVoice($v.VoiceInfo.Name); break "
                "  } "
                "} "
            )
        ps_cmd = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"{voice_select}"
            f'$s.Speak("{safe}")'
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, timeout=45,
        )
        return True
    except Exception as e:
        logger.error("SAPI TTS failed: %s", e)
        return False


class TextToSpeech:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._thread: threading.Thread | None = None

    @property
    def is_speaking(self) -> bool:
        return _speaking

    def stop(self) -> None:
        _stop_event.set()
        sd.stop()
        logger.info("TTS stopped")

    def _resolve_language(self, text: str, language: str | Language | None) -> Language:
        if language is not None:
            if isinstance(language, Language):
                return language
            val = str(language).lower()
            if val in ("hi", "hindi"):
                return Language.HINDI
            if val in ("hinglish",):
                return Language.HINGLISH
            if val in ("en", "english"):
                return Language.ENGLISH
        # Auto from text / default setting
        detected = detect_language(text)
        if detected != Language.ENGLISH:
            return detected
        default = (self._settings.default_language or "en").lower()
        if default == "hi":
            return Language.HINDI
        if default == "hinglish":
            return Language.HINGLISH
        return Language.ENGLISH

    def speak(self, text: str, block: bool = True, language: str | Language | None = None) -> None:
        if not text or not self._settings.tts_enabled:
            return

        _stop_event.clear()
        lang = self._resolve_language(text, language)

        def _speak():
            global _speaking
            _speaking = True
            try:
                # Hindi Devanagari → prefer SAPI Hindi, else fall back to English Piper
                if lang == Language.HINDI or _has_devanagari(text):
                    if _check_hindi_sapi() and _sapi_speak(text, prefer_hindi=True):
                        return
                    logger.warning("Hindi TTS unavailable — falling back to English engine")
                    # If text is Devanagari and no Hindi voice, try SAPI default anyway
                    if _has_devanagari(text):
                        if _sapi_speak(text, prefer_hindi=False):
                            return
                        # Last resort: skip speaking Devanagari with English Piper (garbled)
                        logger.error("Cannot speak Hindi text without a Hindi voice")
                        return

                # Hinglish (Latin) and English → Piper, then SAPI fallback
                try:
                    voice = get_piper_voice()
                    sample_rate = voice.config.sample_rate

                    audio_chunks = []
                    for chunk in voice.synthesize(text):
                        if _stop_event.is_set():
                            break
                        audio_chunks.append(chunk.audio_int16_array)

                    if _stop_event.is_set() or not audio_chunks:
                        return

                    audio = np.concatenate(audio_chunks).astype(np.float32) / 32768.0
                    device = self._settings.speaker_index
                    sd.play(audio, samplerate=sample_rate, device=device)
                    while sd.get_stream().active:
                        if _stop_event.is_set():
                            sd.stop()
                            break
                        sd.sleep(50)
                except Exception as e:
                    logger.error("TTS error: %s", e)
                    self._fallback_speak(text)
            finally:
                _speaking = False

        if block:
            _speak()
        else:
            self._thread = threading.Thread(target=_speak, daemon=True)
            self._thread.start()

    def _fallback_speak(self, text: str) -> None:
        _sapi_speak(text, prefer_hindi=_has_devanagari(text))

    def preload(self) -> None:
        try:
            get_piper_voice()
        except Exception as e:
            logger.warning("Piper preload failed, will use fallback TTS: %s", e)
        # Probe Hindi SAPI in background-friendly sync call (cached)
        try:
            _check_hindi_sapi()
        except Exception:
            pass


def speak(text: str, block: bool = True, language: str | Language | None = None) -> None:
    tts = TextToSpeech()
    tts.speak(text, block=block, language=language)
