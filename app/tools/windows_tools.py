"""Windows system controls."""

from __future__ import annotations

import ctypes
import subprocess
from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition


def _volume_control(args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "up").lower()
    try:
        from pycaw.pycaw import AudioUtilities

        speakers = AudioUtilities.GetSpeakers()
        volume = speakers.EndpointVolume

        if action == "mute":
            volume.SetMute(1, None)
            return {"success": True, "message": "Muted."}
        if action == "unmute":
            volume.SetMute(0, None)
            return {"success": True, "message": "Unmuted."}
        if action == "up":
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(min(1.0, current + 0.1), None)
            return {"success": True, "message": "Volume increased."}
        if action == "down":
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(max(0.0, current - 0.1), None)
            return {"success": True, "message": "Volume decreased."}
        return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        # Fallback: Windows volume media keys via keybd_event
        try:
            import ctypes
            VK = {"mute": 0xAD, "up": 0xAF, "down": 0xAE}
            vk = VK.get(action if action != "unmute" else "mute")
            if vk is None:
                return {"success": False, "error": str(e)}
            # unmute = toggle mute twice if currently muted is unknown; send mute toggle once for mute/unmute
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            return {"success": True, "message": f"Volume {action}."}
        except Exception as e2:
            return {"success": False, "error": f"{e}; fallback failed: {e2}"}


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
