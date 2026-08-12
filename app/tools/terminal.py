"""Terminal command execution with safety layer."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Any

from app.config import get_settings
from app.tools.registry import RiskLevel, ToolDefinition

DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b", r"\bdel\s+/[sfq]", r"\bformat\b", r"\bshutdown\b",
    r"\brestart\b", r"\breboot\b", r"\breg\s+(add|delete|import)\b",
    r"\bdiskpart\b", r"\bbcdedit\b", r"\bmkfs\b", r"\bdd\s+if=",
    r"\bRemove-Item\s+-Recurse\s+-Force\b", r"\bStop-Computer\b",
    r"\bRestart-Computer\b", r">\s*/dev/", r"\|\s*sh\b",
]

SAFE_COMMANDS = {
    "git status", "git log", "git diff", "git branch",
    "npm install", "npm run dev", "npm run build", "npm start", "npm test",
    "python --version", "node --version", "pip list",
}


def _is_dangerous(command: str) -> bool:
    cmd_lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True
    return False


def _needs_confirmation(command: str) -> bool:
    cmd_lower = command.lower().strip()
    if _is_dangerous(command):
        return True
    confirm_keywords = ["push", "install", "uninstall", "remove", "delete", "drop"]
    return any(kw in cmd_lower for kw in confirm_keywords)


def _run_command(args: dict[str, Any]) -> dict[str, Any]:
    command = args.get("command", "")
    cwd = args.get("cwd")

    if not command:
        return {"success": False, "error": "No command specified."}

    if cwd:
        project = cwd.lower()
        projects = get_settings().load_projects()
        cwd = projects.get(project, cwd)

    if not os.path.isdir(cwd or ""):
        cwd = None

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=120, cwd=cwd,
        )
        output = (result.stdout + result.stderr).strip()
        if len(output) > 1000:
            output = output[:1000] + "..."
        return {
            "success": result.returncode == 0,
            "output": output,
            "return_code": result.returncode,
            "message": output if output else f"Command completed with code {result.returncode}.",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 120 seconds."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _git_status(args: dict[str, Any]) -> dict[str, Any]:
    project = args.get("project", "")
    cwd = None
    if project:
        projects = get_settings().load_projects()
        cwd = projects.get(project.lower())
    return _run_command({"command": "git status", "cwd": cwd})


def _start_project(args: dict[str, Any]) -> dict[str, Any]:
    project = args.get("project", "").lower()
    projects = get_settings().load_projects()
    cwd = projects.get(project)
    if not cwd:
        return {"success": False, "error": f"Project '{project}' not found."}
    script = args.get("script", "dev")
    return _run_command({"command": f"npm run {script}", "cwd": cwd})


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="run_terminal_command",
        description="Run a terminal/shell command in a project directory",
        parameters={
            "command": {"type": "string"},
            "cwd": {"type": "string", "description": "Working directory or project name"},
        },
        required=["command"],
        risk_level=RiskLevel.CONFIRMATION_REQUIRED,
        execute=_run_command,
    ))
    registry.register(ToolDefinition(
        name="git_status", description="Check git status for a project",
        parameters={"project": {"type": "string"}},
        required=[], risk_level=RiskLevel.SAFE, execute=_git_status,
    ))
    registry.register(ToolDefinition(
        name="start_project", description="Start a project (npm run dev/build)",
        parameters={
            "project": {"type": "string"},
            "script": {"type": "string", "description": "npm script name (dev, build, etc.)"},
        },
        required=["project"], risk_level=RiskLevel.SAFE, execute=_start_project,
    ))


def classify_command_risk(command: str) -> RiskLevel:
    if _is_dangerous(command):
        return RiskLevel.DANGEROUS
    if _needs_confirmation(command):
        return RiskLevel.CONFIRMATION_REQUIRED
    return RiskLevel.SAFE
