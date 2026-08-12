"""Local speech-to-text using faster-whisper."""

from __future__ import annotations

import threading

import numpy as np

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("stt")

_model = None
_model_lock = threading.Lock()


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


class SpeechToText:
    def __init__(self) -> None:
        self._settings = get_settings()

    def transcribe(self, audio: np.ndarray, sample_rate: int | None = None) -> str:
        if len(audio) == 0:
            return ""

        sr = sample_rate or self._settings.audio_sample_rate
        model = get_whisper_model()

        # faster-whisper expects float32 mono 16kHz
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        segments, info = model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info("Transcribed: %s", text[:100] if text else "(empty)")
        return text

    def transcribe_file(self, path: str) -> str:
        model = get_whisper_model()
        segments, _ = model.transcribe(path, language="en")
        return " ".join(seg.text.strip() for seg in segments).strip()

    def preload(self) -> None:
        get_whisper_model()
