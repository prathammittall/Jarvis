"""Application launching and control for Windows — optimized for low latency."""

from __future__ import annotations

import os
import shutil
import subprocess
import winreg
from typing import Any

from app.core.logger import get_logger
from app.tools import app_catalog
from app.tools.registry import RiskLevel, ToolDefinition

logger = get_logger("applications")

# In-memory cache: app alias -> resolved path or shell name
_path_cache: dict[str, str] = {}


def _expand(path: str) -> str:
    return os.path.expandvars(path)


def _app_paths_registry(exe_name: str) -> str | None:
    """Lookup HKLM/HKCU App Paths — fast, no filesystem walk."""
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"),
        (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"),
    ]
    for hive, key_path in keys:
        try:
            with winreg.OpenKey(hive, key_path) as key:
                path, _ = winreg.QueryValueEx(key, "")
                if path and os.path.isfile(path):
                    return path
        except OSError:
            continue
    return None


def _probe_known(exe_name: str) -> str | None:
    for candidate in app_catalog.known_paths().get(exe_name, []):
        path = _expand(candidate)
        if os.path.isfile(path):
            return path
    return None


def _which_fast(exe_name: str) -> str | None:
    found = shutil.which(exe_name)
    if found and os.path.isfile(found):
        return found
    return None


def _find_executable(name: str) -> str | None:
    """Resolve an app to a launchable path/name without walking Program Files."""
    name_lower = name.lower().strip()
    if name_lower in _path_cache:
        return _path_cache[name_lower]

    if name_lower.endswith(".exe") and os.path.isfile(name):
        _path_cache[name_lower] = name
        return name

    candidates = app_catalog.alias_map().get(
        name_lower,
        [name if name_lower.endswith(".exe") else f"{name_lower}.exe", name],
    )

    for cand in candidates:
        exe = cand if cand.lower().endswith(".exe") else None

        # 1) Known install paths
        if exe:
            path = _probe_known(exe)
            if path:
                _path_cache[name_lower] = path
                return path

        # 2) App Paths registry (exact key)
        if exe:
            path = _app_paths_registry(exe)
            if path:
                _path_cache[name_lower] = path
                return path

        # 3) PATH lookup only (no directory walk)
        check = exe or cand
        path = _which_fast(check)
        if path:
            _path_cache[name_lower] = path
            return path

    # 4) Fall back to bare exe / alias — Windows `start` often resolves these
    fallback = candidates[0]
    _path_cache[name_lower] = fallback
    return fallback


def _launch(path: str) -> None:
    """Fire-and-forget launch."""
    if path.lower().endswith(".lnk"):
        os.startfile(path)
        return
    # Shell builtins / PATH names: use start so Windows resolves them
    if not os.path.isabs(path) or not os.path.isfile(path):
        # Discord special-case: Update.exe --processStart Discord.exe
        if path.lower().endswith("update.exe") and "discord" in path.lower():
            subprocess.Popen([path, "--processStart", "Discord.exe"], shell=False)
            return
        subprocess.Popen(f'start "" "{path}"', shell=True)
        return
    subprocess.Popen([path], shell=False)


def _open_app(args: dict[str, Any]) -> dict[str, Any]:
    app = args.get("application", "")
    if not app:
        return {"success": False, "error": "No application specified."}

    path = _find_executable(app)
    display = app_catalog.display_name(app)
    try:
        if path:
            _launch(path)
            logger.info("Opened %s via %s", app, path)
            return {"success": True, "message": f"Opening {display}."}
        os.startfile(app)
        return {"success": True, "message": f"Opened {display}."}
    except OSError as e:
        _path_cache.pop(app.lower().strip(), None)
        try:
            subprocess.Popen(f'start "" "{app}"', shell=True)
            return {"success": True, "message": f"Opening {display}."}
        except Exception:
            return {"success": False, "error": f"Could not find application: {app} ({e})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _close_app(args: dict[str, Any]) -> dict[str, Any]:
    app = args.get("application", "")
    if not app:
        return {"success": False, "error": "No application specified."}
    exe = app_catalog.close_exe(app)
    display = app_catalog.display_name(app)
    try:
        result = subprocess.run(
            ["taskkill", "/IM", exe, "/F"], capture_output=True, timeout=5, text=True,
        )
        if result.returncode != 0 and "not found" in (result.stderr or "").lower():
            return {"success": False, "error": f"{display} is not running."}
        return {"success": True, "message": f"Closed {display}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _restart_app(args: dict[str, Any]) -> dict[str, Any]:
    app = args.get("application", "")
    if not app:
        return {"success": False, "error": "No application specified."}
    closed = _close_app({"application": app})
    import time
    time.sleep(0.4)
    opened = _open_app({"application": app})
    display = app_catalog.display_name(app)
    if opened.get("success"):
        return {"success": True, "message": f"Restarting {display}."}
    return {
        "success": False,
        "error": opened.get("error") or closed.get("error") or f"Could not restart {display}.",
    }


def _open_project(args: dict[str, Any]) -> dict[str, Any]:
    from app.config import get_settings
    project = args.get("project", "").lower()
    projects = get_settings().load_projects()
    path = projects.get(project) or args.get("path")
    if not path or not os.path.isdir(path):
        return {"success": False, "error": f"Project '{project}' not found. Configure it in config/projects.json."}

    editor = args.get("editor", "vscode")
    if editor in ("vscode", "code", "vs code"):
        code = _find_executable("code")
        if code and os.path.isfile(code):
            subprocess.Popen([code, path])
        else:
            # `code` CLI is often on PATH
            subprocess.Popen(f'code "{path}"', shell=True)
    else:
        os.startfile(path)
    return {"success": True, "message": f"Opening project {project}.", "path": path}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="open_application",
        description="Open/launch a desktop application (Chrome, VS Code, File Explorer, etc.)",
        parameters={"application": {"type": "string", "description": "Application name or alias"}},
        required=["application"],
        risk_level=RiskLevel.SAFE,
        execute=_open_app,
    ))
    registry.register(ToolDefinition(
        name="close_application",
        description="Close a running application",
        parameters={"application": {"type": "string", "description": "Application name"}},
        required=["application"],
        risk_level=RiskLevel.SAFE,
        execute=_close_app,
    ))
    registry.register(ToolDefinition(
        name="restart_application",
        description="Restart a desktop application (close then open)",
        parameters={"application": {"type": "string", "description": "Application name or alias"}},
        required=["application"],
        risk_level=RiskLevel.SAFE,
        execute=_restart_app,
    ))
    registry.register(ToolDefinition(
        name="open_project",
        description="Open a configured developer project in VS Code or File Explorer",
        parameters={
            "project": {"type": "string", "description": "Project name from config/projects.json"},
            "editor": {"type": "string", "description": "Editor to use (vscode or explorer)"},
        },
        required=["project"],
        risk_level=RiskLevel.SAFE,
        execute=_open_project,
    ))
