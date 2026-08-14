"""Register / unregister Jarvis to start with Windows (Startup folder shortcut)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.config import PROJECT_ROOT
from app.core.logger import get_logger

logger = get_logger("startup")

SHORTCUT_NAME = "Jarvis.lnk"


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path() -> Path:
    return _startup_dir() / SHORTCUT_NAME


def is_enabled() -> bool:
    return shortcut_path().exists()


def launch_executable() -> Path:
    """pythonw.exe when available so no console window appears at login."""
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return exe


def launch_script() -> Path:
    return PROJECT_ROOT / "run_jarvis.py"


def enable() -> bool:
    """Create a Startup shortcut that launches Jarvis hidden to the tray."""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        logger.error("pywin32 is required to manage Windows startup")
        return False

    path = shortcut_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    target = str(launch_executable())
    script = str(launch_script())
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(path))
        shortcut.Targetpath = target
        shortcut.Arguments = f'"{script}"'
        shortcut.WorkingDirectory = str(PROJECT_ROOT)
        shortcut.WindowStyle = 7  # minimized
        shortcut.Description = "Jarvis desktop assistant"
        shortcut.save()
        logger.info("Windows startup enabled: %s", path)
        return True
    except Exception as e:
        logger.error("Failed to enable Windows startup: %s", e)
        return False


def disable() -> bool:
    path = shortcut_path()
    try:
        if path.exists():
            path.unlink()
            logger.info("Windows startup disabled")
        return True
    except OSError as e:
        logger.error("Failed to disable Windows startup: %s", e)
        return False


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()
