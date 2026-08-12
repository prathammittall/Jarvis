"""Test Ollama connection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    from app.brain.ollama_client import OllamaClient
    client = OllamaClient()
    health = client.health_check()
    print(f"Running: {health['running']}")
    print(f"Models: {health['models']}")
    print(f"Selected: {health['selected_model']}")
    if health.get("error"):
        print(f"Error: {health['error']}")
        return 1
    if health["running"]:
        print("\nSending test prompt...")
        response = client.generate("Say 'JARVIS online' in exactly those words.")
        print(f"Response: {response}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
