"""Setup script for JARVIS."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    print("JARVIS Setup")
    print("=" * 40)

    venv_path = PROJECT_ROOT / ".venv"
    if not venv_path.exists():
        print("\n1. Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    else:
        print("\n1. Virtual environment exists.")

    pip = venv_path / "Scripts" / "pip.exe"
    if not pip.exists():
        pip = venv_path / "bin" / "pip"

    print("\n2. Installing dependencies...")
    subprocess.run([str(pip), "install", "-r", str(PROJECT_ROOT / "requirements.txt")], check=True)

    print("\n3. Downloading models...")
    python = venv_path / "Scripts" / "python.exe"
    if not python.exists():
        python = venv_path / "bin" / "python"
    subprocess.run([str(python), str(PROJECT_ROOT / "scripts" / "download_models.py")])

    print("\n4. Installing Playwright browsers...")
    subprocess.run([str(python), "-m", "playwright", "install", "chromium"], check=False)

    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        import shutil
        shutil.copy(PROJECT_ROOT / ".env.example", env_file)
        print("\n5. Created .env from .env.example")

    print("\n6. Running system check...")
    subprocess.run([str(python), str(PROJECT_ROOT / "scripts" / "check_system.py")])

    print("\nSetup complete!")
    print(f"\nTo start JARVIS:")
    print(f"  .venv\\Scripts\\activate")
    print(f"  python run_jarvis.py")


if __name__ == "__main__":
    main()
