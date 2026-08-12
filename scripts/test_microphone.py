"""Test microphone access."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    import sounddevice as sd
    import numpy as np

    print("Available input devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}")

    print("\nRecording 3 seconds... Speak now!")
    audio = sd.rec(int(16000 * 3), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    rms = np.sqrt(np.mean(audio ** 2))
    print(f"Recording complete. RMS level: {rms:.4f}")
    if rms > 0.001:
        print("Microphone: WORKING")
    else:
        print("Microphone: Very quiet or not working")

if __name__ == "__main__":
    main()
