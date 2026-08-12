"""Wake word detection using openWakeWord."""

from __future__ import annotations

import threading
from typing import Callable

import numpy as np
import sounddevice as sd

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("wakeword")

_model = None
_model_lock = threading.Lock()


def get_wake_word_model():
    global _model
    with _model_lock:
        if _model is None:
            import openwakeword
            from openwakeword.model import Model
            settings = get_settings()
            openwakeword.utils.download_models([settings.wake_word_model])
            _model = Model(
                wakeword_models=[settings.wake_word_model],
                inference_framework="onnx",
            )
            logger.info("Loaded wake word model: %s", settings.wake_word_model)
        return _model


class WakeWordDetector:
    """Continuous wake word listener using openWakeWord."""

    def __init__(self, on_detected: Callable[[], None] | None = None) -> None:
        self._settings = get_settings()
        self._on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word detector started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("Wake word detector stopped")

    def _listen_loop(self) -> None:
        settings = self._settings
        sample_rate = 16000  # openWakeWord requires 16kHz
        chunk_size = 1280  # 80ms at 16kHz

        try:
            model = get_wake_word_model()
        except Exception as e:
            logger.error("Failed to load wake word model: %s", e)
            return

        def audio_callback(indata, frames, time_info, status):
            if not self._running or not self._enabled:
                return
            audio = indata[:, 0]
            prediction = model.predict(audio)
            for mdl_name, score in prediction.items():
                if score >= settings.wake_word_threshold:
                    logger.info("Wake word detected: %s (score=%.2f)", mdl_name, score)
                    if self._on_detected:
                        self._on_detected()

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_size,
                device=settings.microphone_index,
                callback=audio_callback,
            ):
                while self._running:
                    sd.sleep(100)
        except Exception as e:
            logger.error("Wake word audio stream error: %s", e)


class WhisperWakeWordDetector:
    """Fallback wake word using VAD + tiny Whisper for 'Jarvis' keyword."""

    KEYWORDS = {"jarvis", "hey jarvis", "ok jarvis"}

    def __init__(self, on_detected: Callable[[], None] | None = None) -> None:
        self._settings = get_settings()
        self._on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        self._enabled = True
        self._cooldown = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _listen_loop(self) -> None:
        from app.wakeword.audio import AudioCapture
        from app.speech.stt import SpeechToText

        capture = AudioCapture()
        stt = SpeechToText()
        import time

        while self._running:
            if not self._enabled or self._cooldown:
                time.sleep(0.2)
                continue
            try:
                audio = capture.record_fixed(2.0)
                rms = np.sqrt(np.mean(audio ** 2))
                if rms < 0.005:
                    continue
                text = stt.transcribe(audio).lower().strip()
                if any(kw in text for kw in self.KEYWORDS):
                    logger.info("Whisper wake word detected: %s", text)
                    self._cooldown = True
                    if self._on_detected:
                        self._on_detected()
                    time.sleep(3)
                    self._cooldown = False
            except Exception as e:
                logger.error("Whisper wake word error: %s", e)
                time.sleep(1)


def create_detector(on_detected: Callable[[], None] | None = None):
    settings = get_settings()
    if settings.wake_word_engine == "whisper":
        return WhisperWakeWordDetector(on_detected)
    return WakeWordDetector(on_detected)
