"""Application launching and control for Windows."""

from __future__ import annotations

import os
import subprocess
import winreg
from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition

# Aliases -> search terms or known paths
APP_ALIASES: dict[str, list[str]] = {
    "chrome": ["Google Chrome", "chrome.exe"],
    "google chrome": ["Google Chrome", "chrome.exe"],
    "edge": ["Microsoft Edge", "msedge.exe"],
    "microsoft edge": ["Microsoft Edge", "msedge.exe"],
    "firefox": ["Mozilla Firefox", "firefox.exe"],
    "vscode": ["Visual Studio Code", "Code.exe"],
    "vs code": ["Visual Studio Code", "Code.exe"],
    "visual studio code": ["Visual Studio Code", "Code.exe"],
    "code": ["Visual Studio Code", "Code.exe"],
    "terminal": ["Windows Terminal", "wt.exe"],
    "windows terminal": ["Windows Terminal", "wt.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["Calculator", "calc.exe"],
    "calc": ["Calculator", "calc.exe"],
    "spotify": ["Spotify", "Spotify.exe"],
    "discord": ["Discord", "Discord.exe"],
}


def _find_in_registry(app_name: str) -> str | None:
    """Search Windows registry for application path."""
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    for hive, base in keys:
        try:
            with winreg.OpenKey(hive, base) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subname = winreg.EnumKey(key, i)
                    if app_name.lower() in subname.lower():
                        with winreg.OpenKey(key, subname) as sub:
                            path, _ = winreg.QueryValueEx(sub, "")
                            if os.path.exists(path):
                                return path
        except OSError:
            pass
    return None


def _find_executable(name: str) -> str | None:
    """Find application executable path."""
    name_lower = name.lower().strip()

    # Direct exe
    if name_lower.endswith(".exe") and os.path.exists(name):
        return name

    # Known aliases
    aliases = APP_ALIASES.get(name_lower, [name])
    for alias in aliases:
        if alias.endswith(".exe"):
            # Search PATH and common locations
            found = _search_exe(alias)
            if found:
                return found
            # Try start command (Windows resolves these)
            return alias
        path = _find_in_registry(alias)
        if path:
            return path
        found = _search_exe(f"{alias}.exe") if not alias.endswith(".exe") else _search_exe(alias)
        if found:
            return found

    # Search Start Menu
    start_paths = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for sp in start_paths:
        for root, _, files in os.walk(sp):
            for f in files:
                if f.lower().endswith(".lnk") and name_lower in f.lower():
                    return os.path.join(root, f)

    return None


def _search_exe(exe_name: str) -> str | None:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    common = [
        os.path.expandvars(r"%ProgramFiles%"),
        os.path.expandvars(r"%ProgramFiles(x86)%"),
        os.path.expandvars(r"%LOCALAPPDATA%"),
    ]
    for base in paths + common:
        for root, _, files in os.walk(base) if base in common else [("", [], [exe_name])]:
            if base in common:
                if exe_name.lower() in [f.lower() for f in files]:
                    return os.path.join(root, exe_name)
            else:
                candidate = os.path.join(base, exe_name)
                if os.path.isfile(candidate):
                    return candidate
    return None


def _open_app(args: dict[str, Any]) -> dict[str, Any]:
    app = args.get("application", "")
    if not app:
        return {"success": False, "error": "No application specified."}

    path = _find_executable(app)
    if path is None:
        # Try os.startfile / start command as last resort
        try:
            os.startfile(app)
            return {"success": True, "message": f"Opened {app}."}
        except OSError:
            return {"success": False, "error": f"Could not find application: {app}"}

    try:
        if path.endswith(".lnk"):
            os.startfile(path)
        elif path.endswith(".exe") and not os.path.isabs(path):
            subprocess.Popen(["start", "", path], shell=True)
        else:
            subprocess.Popen([path], shell=False)
        display = app.replace("_", " ").title()
        return {"success": True, "message": f"Opening {display}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _close_app(args: dict[str, Any]) -> dict[str, Any]:
    app = args.get("application", "")
    exe_map = {
        "chrome": "chrome.exe", "firefox": "firefox.exe", "edge": "msedge.exe",
        "vscode": "Code.exe", "vs code": "Code.exe", "spotify": "Spotify.exe",
        "discord": "Discord.exe", "notepad": "notepad.exe",
    }
    exe = exe_map.get(app.lower(), f"{app}.exe" if not app.endswith(".exe") else app)
    try:
        subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True, timeout=10)
        return {"success": True, "message": f"Closed {app}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
            os.startfile(path)
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
