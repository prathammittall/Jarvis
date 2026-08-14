"""Configurable application / website / folder catalog.

Defaults live here so Jarvis still works without config/apps.json.
Extra apps and overrides are merged from that file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from app.core.logger import get_logger

logger = get_logger("app_catalog")

DEFAULT_APPS: dict[str, dict[str, Any]] = {
    "chrome": {
        "aliases": ["chrome", "google chrome", "browser"],
        "exe": ["chrome.exe", "Google Chrome"],
        "display": "Chrome",
        "close_exe": "chrome.exe",
        "confirm_close": False,
        "known_paths": [
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
    },
    "edge": {
        "aliases": ["edge", "microsoft edge"],
        "exe": ["msedge.exe", "Microsoft Edge"],
        "display": "Edge",
        "close_exe": "msedge.exe",
        "confirm_close": False,
        "known_paths": [
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "firefox": {
        "aliases": ["firefox", "mozilla firefox"],
        "exe": ["firefox.exe", "Mozilla Firefox"],
        "display": "Firefox",
        "close_exe": "firefox.exe",
        "confirm_close": False,
        "known_paths": [
            r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
            r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
        ],
    },
    "vscode": {
        "aliases": ["vscode", "vs code", "visual studio code", "code"],
        "exe": ["Code.exe", "code"],
        "display": "VS Code",
        "close_exe": "Code.exe",
        "confirm_close": False,
        "known_paths": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%ProgramFiles%\Microsoft VS Code\Code.exe",
        ],
    },
    "spotify": {
        "aliases": ["spotify"],
        "exe": ["Spotify.exe"],
        "display": "Spotify",
        "close_exe": "Spotify.exe",
        "confirm_close": False,
        "known_paths": [r"%APPDATA%\Spotify\Spotify.exe"],
    },
    "discord": {
        "aliases": ["discord"],
        "exe": ["Discord.exe"],
        "display": "Discord",
        "close_exe": "Discord.exe",
        "confirm_close": False,
        "known_paths": [r"%LOCALAPPDATA%\Discord\Update.exe"],
    },
    "notepad": {
        "aliases": ["notepad"],
        "exe": ["notepad.exe"],
        "display": "Notepad",
        "close_exe": "notepad.exe",
        "confirm_close": False,
        "known_paths": [],
    },
    "calculator": {
        "aliases": ["calculator", "calc"],
        "exe": ["calc.exe"],
        "display": "Calculator",
        "close_exe": "CalculatorApp.exe",
        "confirm_close": False,
        "known_paths": [],
    },
    "explorer": {
        "aliases": ["explorer", "file explorer", "files"],
        "exe": ["explorer.exe"],
        "display": "File Explorer",
        "close_exe": "explorer.exe",
        "confirm_close": True,
        "known_paths": [],
    },
    "terminal": {
        "aliases": ["terminal", "windows terminal", "cmd", "command prompt", "powershell"],
        "exe": ["wt.exe", "WindowsTerminal.exe", "cmd.exe", "powershell.exe"],
        "display": "Terminal",
        "close_exe": "WindowsTerminal.exe",
        "confirm_close": False,
        "known_paths": [],
    },
}

DEFAULT_WEBSITES: dict[str, str] = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
}

DEFAULT_FOLDERS: dict[str, str] = {
    "downloads": "downloads",
    "documents": "documents",
    "desktop": "desktop",
    "download": "downloads",
    "docs": "documents",
}

_cache: dict[str, Any] | None = None


def _deep_merge_app(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in ("aliases", "exe", "known_paths") and isinstance(value, list):
            existing = list(merged.get(key) or [])
            for item in value:
                if item not in existing:
                    existing.append(item)
            merged[key] = existing
        else:
            merged[key] = value
    return merged


def load_catalog(force: bool = False) -> dict[str, Any]:
    global _cache
    if _cache is not None and not force:
        return _cache

    apps = {k: dict(v) for k, v in DEFAULT_APPS.items()}
    websites = dict(DEFAULT_WEBSITES)
    folders = dict(DEFAULT_FOLDERS)

    settings = get_settings()
    path = PROJECT_ROOT / getattr(settings, "apps_config", "config/apps.json")
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for name, spec in (data.get("apps") or {}).items():
                key = name.lower().strip()
                if key in apps:
                    apps[key] = _deep_merge_app(apps[key], spec)
                else:
                    apps[key] = spec
            websites.update({k.lower(): v for k, v in (data.get("websites") or {}).items()})
            folders.update({k.lower(): v for k, v in (data.get("folders") or {}).items()})
            logger.info("Loaded app catalog from %s (%d apps)", path.name, len(apps))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load %s: %s", path, e)

    _cache = {"apps": apps, "websites": websites, "folders": folders}
    return _cache


def reload_catalog() -> dict[str, Any]:
    return load_catalog(force=True)


def resolve_app_key(name: str) -> str | None:
    n = (name or "").lower().strip()
    if not n:
        return None
    apps = load_catalog()["apps"]
    if n in apps:
        return n
    for key, spec in apps.items():
        aliases = [a.lower() for a in spec.get("aliases") or []]
        display = str(spec.get("display") or "").lower()
        if n == display or n in aliases:
            return key
        if n + ".exe" in [e.lower() for e in spec.get("exe") or []]:
            return key
    return None


def get_app(name: str) -> dict[str, Any] | None:
    key = resolve_app_key(name)
    if not key:
        return None
    return load_catalog()["apps"].get(key)


def display_name(name: str) -> str:
    spec = get_app(name)
    if spec and spec.get("display"):
        return str(spec["display"])
    return (name or "").replace("_", " ").title()


def close_exe(name: str) -> str:
    spec = get_app(name)
    if spec and spec.get("close_exe"):
        return str(spec["close_exe"])
    if name.lower().endswith(".exe"):
        return name
    return f"{name}.exe"


def requires_close_confirmation(name: str) -> bool:
    spec = get_app(name)
    return bool(spec and spec.get("confirm_close"))


def alias_map() -> dict[str, list[str]]:
    """alias / key → list of exe names (for launcher)."""
    out: dict[str, list[str]] = {}
    for key, spec in load_catalog()["apps"].items():
        exes = list(spec.get("exe") or [f"{key}.exe"])
        out[key] = exes
        for alias in spec.get("aliases") or []:
            out[str(alias).lower()] = exes
    return out


def known_paths() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in load_catalog()["apps"].values():
        for exe in spec.get("exe") or []:
            if str(exe).lower().endswith(".exe"):
                paths = list(spec.get("known_paths") or [])
                if paths:
                    out[exe] = paths
    return out


def website_url(name: str) -> str | None:
    n = (name or "").lower().strip()
    return load_catalog()["websites"].get(n)


def folder_key(name: str) -> str | None:
    n = (name or "").lower().strip()
    folders = load_catalog()["folders"]
    if n in folders:
        return folders[n]
    if n.startswith("my "):
        return folders.get(n[3:])
    return None


def speech_aliases() -> dict[str, str]:
    """Speech alias → canonical app key (for the fast intent parser)."""
    out: dict[str, str] = {}
    for key, spec in load_catalog()["apps"].items():
        out[key] = key
        display = str(spec.get("display") or "").lower()
        if display:
            out[display] = key
        for alias in spec.get("aliases") or []:
            out[str(alias).lower()] = key
    return out


def website_aliases() -> dict[str, str]:
    return {k: k for k in load_catalog()["websites"]}
