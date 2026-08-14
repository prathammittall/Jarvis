"""Quick local microphone check (no audio is uploaded)."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.config import get_settings
from app.core.logger import get_logger

logger = get_logger("mic_test")


def test_microphone(duration: float = 2.0) -> dict[str, Any]:
    """Record a short clip and report whether the mic is picking up sound."""
    try:
        import sounddevice as sd
    except Exception as e:
        return {"ok": False, "message": f"Audio library unavailable: {e}", "rms": 0.0}

    settings = get_settings()
    sample_rate = settings.audio_sample_rate or 16000
    device = settings.microphone_index
    try:
        audio = sd.rec(
            int(sample_rate * duration),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=device,
        )
        sd.wait()
        samples = audio[:, 0] if audio.ndim > 1 else audio
        rms = float(np.sqrt(np.mean(np.square(samples))))
        if rms > 0.008:
            msg = f"Microphone is working (level {rms:.3f})."
            ok = True
        elif rms > 0.001:
            msg = f"Microphone is quiet (level {rms:.3f}). Try speaking louder."
            ok = True
        else:
            msg = "Microphone is very quiet or not receiving audio."
            ok = False
        logger.info("Mic test: rms=%.4f ok=%s", rms, ok)
        return {"ok": ok, "message": msg, "rms": rms}
    except Exception as e:
        logger.error("Mic test failed: %s", e)
        return {"ok": False, "message": f"Could not access the microphone: {e}", "rms": 0.0}
