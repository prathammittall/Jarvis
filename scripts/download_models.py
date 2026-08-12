"""Download required models for JARVIS."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def download_piper_voice():
    from app.speech.tts import _download_piper_voice
    from app.config import get_settings
    settings = get_settings()
    settings.piper_model_dir.mkdir(parents=True, exist_ok=True)
    path = _download_piper_voice(settings.tts_voice)
    if path:
        print(f"Piper voice downloaded: {path}")
    else:
        print("Failed to download Piper voice.")


def download_wake_word():
    try:
        import openwakeword
        from app.config import get_settings
        settings = get_settings()
        openwakeword.utils.download_models([settings.wake_word_model])
        print(f"Wake word model downloaded: {settings.wake_word_model}")
    except Exception as e:
        print(f"Wake word download failed: {e}")


def main():
    print("Downloading JARVIS models...")
    print("\n1. Piper TTS voice...")
    download_piper_voice()
    print("\n2. Wake word model...")
    download_wake_word()
    print("\n3. Whisper model will download on first use.")
    print("\n4. Ollama model - run manually:")
    print("   ollama pull qwen3:4b")
    print("\nDone.")


if __name__ == "__main__":
    main()
