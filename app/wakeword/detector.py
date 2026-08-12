"""Wake word detection using openWakeWord (with Whisper fallback)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("wakeword")

_model = None
_model_lock = threading.Lock()


def _ensure_openwakeword_models() -> Path:
    """Ensure ONNX feature + wake-word models exist; download if needed."""
    import openwakeword
    from openwakeword.utils import download_file

    models_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # Feature models: tflite may exist while onnx is missing (upstream skip bug)
    feature_files = {
        "embedding_model.onnx": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx",
        "melspectrogram.onnx": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx",
    }
    for name, url in feature_files.items():
        path = models_dir / name
        if not path.exists():
            logger.info("Downloading %s...", name)
            download_file(url, str(models_dir))

    required = ["embedding_model.onnx", "melspectrogram.onnx", "hey_jarvis_v0.1.onnx"]
    if not (models_dir / "hey_jarvis_v0.1.onnx").exists():
        openwakeword.utils.download_models(["hey_jarvis_v0.1"])

    still_missing = [name for name in required if not (models_dir / name).exists()]
    if still_missing:
        raise FileNotFoundError(f"Wake word models still missing: {still_missing}")
    return models_dir


def get_wake_word_model():
    global _model
    with _model_lock:
        if _model is None:
            from openwakeword.model import Model

            models_dir = _ensure_openwakeword_models()
            settings = get_settings()
            model_name = settings.wake_word_model
            candidates = [
                models_dir / f"{model_name}.onnx",
                models_dir / f"{model_name}_v0.1.onnx",
                models_dir / "hey_jarvis_v0.1.onnx",
            ]
            model_path = next((p for p in candidates if p.exists()), None)
            if model_path is None:
                raise FileNotFoundError(f"No wake word model found for '{model_name}'")

            _model = Model(
                wakeword_models=[str(model_path)],
                inference_framework="onnx",
            )
            logger.info("Loaded wake word model: %s", model_path.name)
        return _model


class WakeWordDetector:
    """Continuous wake word listener. Releases the mic while paused."""

    def __init__(self, on_detected: Callable[[], None] | None = None) -> None:
        self._settings = get_settings()
        self._on_detected = on_detected
        self._running = False
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = True
        self._stream: sd.InputStream | None = None
        self._stream_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def pause(self) -> None:
        """Close the mic stream so command recording can use it exclusively."""
        self._paused.set()
        self._close_stream()
        logger.info("Wake word mic released")

    def resume(self) -> None:
        self._paused.clear()
        logger.info("Wake word listening resumed")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="wakeword")
        self._thread.start()
        logger.info("Wake word detector started")

    def stop(self) -> None:
        self._running = False
        self._paused.clear()
        self._close_stream()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("Wake word detector stopped")

    def _close_stream(self) -> None:
        with self._stream_lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

    def _listen_loop(self) -> None:
        settings = self._settings
        sample_rate = 16000
        chunk_size = 1280
        threshold = float(settings.wake_word_threshold)

        try:
            model = get_wake_word_model()
        except Exception as e:
            logger.error("Failed to load wake word model: %s", e)
            logger.error("Use the Click to Talk button, or reinstall wake-word models.")
            return

        last_fire = 0.0
        last_score_log = 0.0
        max_recent = 0.0
        logger.info(
            "Wake word ready — say 'Hey Jarvis' (threshold=%.2f, mic=%s)",
            threshold,
            settings.microphone_index,
        )

        while self._running:
            # Wait while paused / disabled
            while self._running and (self._paused.is_set() or not self._enabled):
                time.sleep(0.1)
            if not self._running:
                break

            detected = threading.Event()
            max_recent = 0.0

            def audio_callback(indata, frames, time_info, status):
                nonlocal last_fire, max_recent
                if self._paused.is_set() or not self._enabled or not self._running:
                    return
                if status:
                    logger.warning("Wake word audio status: %s", status)

                pcm = (indata[:, 0] * 32767).astype(np.int16)
                prediction = model.predict(pcm)
                for mdl_name, score in prediction.items():
                    if score >= 0.05:
                        logger.debug("Wake score %s=%.2f", mdl_name, score)
                    if score > max_recent:
                        max_recent = float(score)
                    if score >= threshold and (time.time() - last_fire) > 1.5:
                        last_fire = time.time()
                        logger.info("Wake word detected: %s (score=%.2f)", mdl_name, score)
                        try:
                            model.reset()
                        except Exception:
                            pass
                        detected.set()

            try:
                with self._stream_lock:
                    self._stream = sd.InputStream(
                        samplerate=sample_rate,
                        channels=1,
                        dtype="float32",
                        blocksize=chunk_size,
                        device=settings.microphone_index,
                        callback=audio_callback,
                    )
                    self._stream.start()

                # Poll until detection, pause, or stop
                while self._running and not self._paused.is_set() and self._enabled:
                    if detected.is_set():
                        self._paused.set()
                        self._close_stream()
                        if self._on_detected:
                            self._on_detected()
                        break
                    now = time.time()
                    if now - last_score_log >= 3.0:
                        if max_recent > 0:
                            logger.info("Wake listening… peak score=%.2f (need >=%.2f)", max_recent, threshold)
                        else:
                            logger.debug("Wake listening… no speech scores yet")
                        max_recent = 0.0
                        last_score_log = now
                    time.sleep(0.05)

                self._close_stream()
            except Exception as e:
                logger.error("Wake word audio stream error: %s", e)
                self._close_stream()
                time.sleep(1.0)


class WhisperWakeWordDetector:
    """Listen for 'Jarvis' using a tiny Whisper model (works with single-word)."""

    KEYWORDS = ("jarvis", "hey jarvis", "ok jarvis", "hi jarvis", "yo jarvis")
    # Common Whisper mishearings of "Jarvis"
    FUZZY = ("jarvis", "jarviss", "jarves", "jarvus", "jervis", "gervis")

    def __init__(self, on_detected: Callable[[], None] | None = None) -> None:
        self._settings = get_settings()
        self._on_detected = on_detected
        self._running = False
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = True
        self._tiny_model = None
        self._stream: sd.InputStream | None = None
        self._stream_lock = threading.Lock()
        self._audio_buf: list[np.ndarray] = []
        self._buf_lock = threading.Lock()
        self._samples_ready = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def pause(self) -> None:
        self._paused.set()
        self._close_stream()
        logger.info("Wake word mic released")

    def resume(self) -> None:
        self._paused.clear()
        logger.info("Wake word listening resumed")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused.clear()
        self._thread = threading.Thread(
            target=self._listen_loop, daemon=True, name="wakeword-whisper"
        )
        self._thread.start()
        logger.info("Wake word detector started — say 'Jarvis'")

    def stop(self) -> None:
        self._running = False
        self._paused.clear()
        self._close_stream()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def _close_stream(self) -> None:
        with self._stream_lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
        with self._buf_lock:
            self._audio_buf.clear()
            self._samples_ready = 0

    def _get_tiny_model(self):
        if self._tiny_model is None:
            from faster_whisper import WhisperModel
            device, compute = "cpu", "int8"
            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    device, compute = "cuda", "float16"
            except Exception:
                pass
            logger.info("Loading tiny Whisper for wake word on %s", device)
            self._tiny_model = WhisperModel("tiny", device=device, compute_type=compute)
        return self._tiny_model

    def _transcribe_chunk(self, audio: np.ndarray) -> str:
        model = self._get_tiny_model()
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        segments, _ = model.transcribe(
            audio,
            language="en",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip().lower()

    @classmethod
    def _matches_wake(cls, text: str) -> bool:
        if not text:
            return False
        cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
        cleaned = " ".join(cleaned.split())
        if any(kw in cleaned for kw in cls.KEYWORDS):
            return True
        tokens = cleaned.split()
        return any(any(f in tok for f in cls.FUZZY) for tok in tokens)

    def _listen_loop(self) -> None:
        settings = self._settings
        sample_rate = 16000
        chunk_size = 1280  # 80ms
        window_samples = int(sample_rate * 1.5)  # ~1.5s analyze window
        hop_samples = int(sample_rate * 0.75)  # re-check every 0.75s
        last_fire = 0.0

        logger.info("Listening for wake word: Jarvis (Whisper)")
        try:
            self._get_tiny_model()
        except Exception as e:
            logger.error("Failed to load Whisper wake model: %s", e)
            return

        while self._running:
            while self._running and (self._paused.is_set() or not self._enabled):
                time.sleep(0.1)
            if not self._running:
                break

            def audio_callback(indata, frames, time_info, status):
                if self._paused.is_set() or not self._enabled or not self._running:
                    return
                if status:
                    logger.warning("Wake word audio status: %s", status)
                chunk = indata[:, 0].copy()
                with self._buf_lock:
                    self._audio_buf.append(chunk)
                    self._samples_ready += len(chunk)
                    # Keep only ~3s of audio
                    max_keep = sample_rate * 3
                    while self._samples_ready > max_keep and self._audio_buf:
                        dropped = self._audio_buf.pop(0)
                        self._samples_ready -= len(dropped)

            try:
                with self._stream_lock:
                    self._stream = sd.InputStream(
                        samplerate=sample_rate,
                        channels=1,
                        dtype="float32",
                        blocksize=chunk_size,
                        device=settings.microphone_index,
                        callback=audio_callback,
                    )
                    self._stream.start()

                next_check = time.time() + 0.8
                while self._running and not self._paused.is_set() and self._enabled:
                    now = time.time()
                    if now < next_check:
                        time.sleep(0.05)
                        continue
                    next_check = now + 0.75

                    with self._buf_lock:
                        if self._samples_ready < window_samples:
                            continue
                        audio = np.concatenate(self._audio_buf)
                        # Use the most recent window
                        audio = audio[-window_samples:]
                        # Drop hop so next window overlaps
                        drop = 0
                        while drop < hop_samples and self._audio_buf:
                            first = self._audio_buf[0]
                            if drop + len(first) <= hop_samples:
                                self._audio_buf.pop(0)
                                self._samples_ready -= len(first)
                                drop += len(first)
                            else:
                                take = hop_samples - drop
                                self._audio_buf[0] = first[take:]
                                self._samples_ready -= take
                                drop += take

                    rms = float(np.sqrt(np.mean(audio ** 2)))
                    if rms < 0.004:
                        continue

                    text = self._transcribe_chunk(audio)
                    if text:
                        logger.info("Wake heard: %r (rms=%.3f)", text, rms)
                    if self._matches_wake(text) and (time.time() - last_fire) > 1.5:
                        last_fire = time.time()
                        logger.info("Wake word detected: %s", text)
                        self._paused.set()
                        self._close_stream()
                        if self._on_detected:
                            self._on_detected()
                        break

                self._close_stream()
            except Exception as e:
                logger.error("Whisper wake word error: %s", e)
                self._close_stream()
                time.sleep(1.0)


def create_detector(on_detected: Callable[[], None] | None = None):
    settings = get_settings()
    engine = (settings.wake_word_engine or "openwakeword").lower().strip()
    if engine == "whisper":
        return WhisperWakeWordDetector(on_detected)
    return WakeWordDetector(on_detected)
