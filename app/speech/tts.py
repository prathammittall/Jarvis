"""Local text-to-speech using Piper."""

from __future__ import annotations

import io
import subprocess
import sys
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.config import PROJECT_ROOT, get_settings
from app.core.logger import get_logger

logger = get_logger("tts")

_voice = None
_voice_lock = threading.Lock()
_stop_event = threading.Event()
_speaking = False


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

    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
    if "lessac" in voice_name:
        urls = {
            onnx_path: f"{base_url}/en_US-lessac-medium.onnx",
            json_path: f"{base_url}/en_US-lessac-medium.onnx.json",
        }
    else:
        logger.warning("Unknown voice '%s', using fallback download for lessac", voice_name)
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

    def speak(self, text: str, block: bool = True) -> None:
        if not text or not self._settings.tts_enabled:
            return

        _stop_event.clear()

        def _speak():
            global _speaking
            _speaking = True
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
                # Fallback to Windows SAPI
                self._fallback_speak(text)
            finally:
                _speaking = False

        if block:
            _speak()
        else:
            self._thread = threading.Thread(target=_speak, daemon=True)
            self._thread.start()

    def _fallback_speak(self, text: str) -> None:
        if sys.platform == "win32":
            try:
                ps_cmd = (
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$s.Speak("{text.replace(chr(34), chr(39))}")'
                )
                subprocess.run(
                    ["powershell", "-Command", ps_cmd],
                    capture_output=True, timeout=30,
                )
            except Exception as e:
                logger.error("Fallback TTS failed: %s", e)

    def preload(self) -> None:
        try:
            get_piper_voice()
        except Exception as e:
            logger.warning("Piper preload failed, will use fallback TTS: %s", e)


def speak(text: str, block: bool = True) -> None:
    tts = TextToSpeech()
    tts.speak(text, block=block)
