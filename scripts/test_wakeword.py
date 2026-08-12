"""Test wake word detection."""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    from app.wakeword.detector import create_detector

    detected = False

    def on_detect():
        nonlocal detected
        detected = True
        print("\n>>> WAKE WORD DETECTED! <<<")

    detector = create_detector(on_detected=on_detect)
    print("Listening for wake word... Say 'Jarvis'")
    print("Press Ctrl+C to stop.")
    detector.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        detector.stop()
        print("\nStopped.")

if __name__ == "__main__":
    main()
