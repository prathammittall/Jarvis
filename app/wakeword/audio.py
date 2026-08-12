"""Audio capture utilities."""

from __future__ import annotations

import threading
from typing import Callable

import numpy as np
import sounddevice as sd

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("audio")


class AudioCapture:
    def __init__(self, sample_rate: int | None = None, device: int | None = None) -> None:
        settings = get_settings()
        self.sample_rate = sample_rate or settings.audio_sample_rate
        self.device = device if device is not None else settings.microphone_index
        self._stream: sd.InputStream | None = None
        self._running = False

    def record_until_silence(
        self,
        max_duration: float | None = None,
        silence_timeout: float | None = None,
        silence_threshold: float = 0.01,
        on_audio: Callable[[np.ndarray], None] | None = None,
    ) -> np.ndarray:
        settings = get_settings()
        max_dur = max_duration or settings.command_max_duration
        silence_to = silence_timeout or settings.command_silence_timeout

        frames: list[np.ndarray] = []
        silent_chunks = 0
        chunk_duration = 0.1
        chunk_size = int(self.sample_rate * chunk_duration)
        max_chunks = int(max_dur / chunk_duration)
        silence_chunks_needed = int(silence_to / chunk_duration)
        speech_started = False

        def callback(indata, frame_count, time_info, status):
            nonlocal silent_chunks, speech_started
            if status:
                logger.warning("Audio status: %s", status)
            chunk = indata[:, 0].copy()
            rms = np.sqrt(np.mean(chunk ** 2))
            if rms > silence_threshold:
                speech_started = True
                silent_chunks = 0
                frames.append(chunk)
            elif speech_started:
                silent_chunks += 1
                frames.append(chunk)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
            blocksize=chunk_size,
            callback=callback,
        ):
            import time
            for _ in range(max_chunks):
                time.sleep(chunk_duration)
                if speech_started and silent_chunks >= silence_chunks_needed:
                    break

        if not frames:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(frames)
        if on_audio:
            on_audio(audio)
        return audio

    def record_fixed(self, duration: float) -> np.ndarray:
        num_samples = int(self.sample_rate * duration)
        audio = sd.rec(
            num_samples,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
        )
        sd.wait()
        return audio[:, 0]

    @staticmethod
    def list_input_devices() -> list[dict]:
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]
