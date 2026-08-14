"""Local speech-to-text using faster-whisper (English / Hindi / Hinglish)."""

from __future__ import annotations

import threading

import numpy as np

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("stt")

_model = None
_model_lock = threading.Lock()

# Bias Whisper toward common Jarvis commands (helps Hinglish romanization)
_INITIAL_PROMPT = (
    "Jarvis commands: open Chrome, Chrome kholo, YouTube kholo, open WhatsApp, "
    "send a WhatsApp message, volume badha do, volume kam karo, "
    "Google pe search karo, notepad kholo, music chalao, shutdown, lock PC, screenshot."
)


def _get_device_and_compute() -> tuple[str, str]:
    settings = get_settings()
    device = settings.whisper_device
    compute = settings.whisper_compute_type

    if device == "auto":
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                device = "cuda"
            else:
                device = "cpu"
        except Exception:
            device = "cpu"

    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"

    return device, compute


def get_whisper_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            settings = get_settings()
            device, compute = _get_device_and_compute()
            logger.info("Loading Whisper model '%s' on %s (%s)", settings.whisper_model, device, compute)
            _model = WhisperModel(settings.whisper_model, device=device, compute_type=compute)
        return _model


def _resolve_whisper_language() -> str | None:
    """
    Map settings to faster-whisper language.
    None = automatic language detection (best for mixed Hindi/English).
    """
    settings = get_settings()
    lang = (settings.whisper_language or "auto").strip().lower()
    if lang in ("", "auto", "detect", "multilingual"):
        return None
    if lang in ("en", "english", "en-in", "en-us", "en-gb"):
        return "en"
    if lang in ("hi", "hindi", "hi-in"):
        return "hi"
    return lang


class SpeechToText:
    def __init__(self) -> None:
        self._settings = get_settings()
        self.last_language: str | None = None
        self.last_latency: float = 0.0

    def transcribe(self, audio: np.ndarray, sample_rate: int | None = None) -> str:
        import time
        if len(audio) == 0:
            return ""

        sr = sample_rate or self._settings.audio_sample_rate
        model = get_whisper_model()

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        language = _resolve_whisper_language()
        start = time.perf_counter()
        segments, info = model.transcribe(
            audio,
            language=language,
            beam_size=1,
            best_of=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 250},
            condition_on_previous_text=False,
            without_timestamps=True,
            initial_prompt=_INITIAL_PROMPT,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        self.last_latency = time.perf_counter() - start
        detected = getattr(info, "language", None) or language or "unknown"
        self.last_language = detected
        logger.info(
            "Transcribed (lang=%s, %.2fs): %s",
            detected,
            self.last_latency,
            text[:100] if text else "(empty)",
        )
        return text

    def transcribe_file(self, path: str) -> str:
        model = get_whisper_model()
        language = _resolve_whisper_language()
        segments, info = model.transcribe(
            path,
            language=language,
            initial_prompt=_INITIAL_PROMPT,
        )
        self.last_language = getattr(info, "language", None)
        return " ".join(seg.text.strip() for seg in segments).strip()

    def preload(self) -> None:
        get_whisper_model()
