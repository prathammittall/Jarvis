"""Test TTS."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    from app.speech.tts import speak
    print("Testing TTS...")
    speak("JARVIS online. Systems operational.")
    print("TTS test complete.")

if __name__ == "__main__":
    main()
