"""Windows system controls."""

from __future__ import annotations

import ctypes
import subprocess
from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition


def _volume_control(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "up").lower()
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        if action == "mute":
            volume.SetMute(1, None)
            return {"success": True, "message": "Muted."}
        elif action == "unmute":
            volume.SetMute(0, None)
            return {"success": True, "message": "Unmuted."}
        elif action == "up":
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(min(1.0, current + 0.1), None)
            return {"success": True, "message": "Volume increased."}
        elif action == "down":
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(max(0.0, current - 0.1), None)
            return {"success": True, "message": "Volume decreased."}
        return {"success": False, "error": f"Unknown action: {action}"}
    except ImportError:
        # Fallback using nircmd or powershell
        ps_map = {"mute": "(New-Object -ComObject WScript.Shell).SendKeys([char]173)",
                  "up": "(New-Object -ComObject WScript.Shell).SendKeys([char]175)",
                  "down": "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"}
        cmd = ps_map.get(action)
        if cmd:
            subprocess.run(["powershell", "-Command", cmd], capture_output=True)
            return {"success": True, "message": f"Volume {action}."}
        return {"success": False, "error": "Volume control unavailable."}


def _lock_computer(args: dict[str, Any]) -> dict[str, Any]:
    ctypes.windll.user32.LockWorkStation()
    return {"success": True, "message": "Computer locked."}


def _shutdown(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "shutdown").lower()
    cmd_map = {
        "shutdown": "shutdown /s /t 5",
        "restart": "shutdown /r /t 5",
        "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
    }
    cmd = cmd_map.get(action)
    if not cmd:
        return {"success": False, "error": f"Unknown action: {action}"}
    subprocess.Popen(cmd, shell=True)
    return {"success": True, "message": f"{action.capitalize()} initiated in 5 seconds."}


def _get_time(args: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime
    now = datetime.now()
    formatted = now.strftime("%I:%M %p on %A, %B %d")
    return {"success": True, "message": f"It's {formatted}.", "time": formatted}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="volume_control",
        description="Control system volume (up, down, mute, unmute)",
        parameters={"action": {"type": "string", "enum": ["up", "down", "mute", "unmute"]}},
        required=["action"], risk_level=RiskLevel.SAFE, execute=_volume_control,
    ))
    registry.register(ToolDefinition(
        name="lock_computer", description="Lock the computer",
        parameters={}, required=[], risk_level=RiskLevel.SAFE, execute=_lock_computer,
    ))
    registry.register(ToolDefinition(
        name="system_power",
        description="Shutdown, restart, or sleep the computer (requires confirmation)",
        parameters={"action": {"type": "string", "enum": ["shutdown", "restart", "sleep"]}},
        required=["action"], risk_level=RiskLevel.CONFIRMATION_REQUIRED, execute=_shutdown,
    ))
    registry.register(ToolDefinition(
        name="get_time", description="Get the current date and time",
        parameters={}, required=[], risk_level=RiskLevel.SAFE, execute=_get_time,
    ))
