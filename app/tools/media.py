"""Media control tools (playback + interrupt)."""

from __future__ import annotations

import ctypes
import sys
from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition

# Windows virtual-key codes for media keys
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_STOP = 0xB2
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _media_key(vk: int) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Media keys are only supported on Windows.")
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


def _stop(args: dict[str, Any]) -> dict[str, Any]:
    from app.speech.tts import TextToSpeech
    TextToSpeech().stop()
    return {"success": True, "message": "Stopped.", "action": "stop"}


def _media_control(args: dict[str, Any]) -> dict[str, Any]:
    action = (args.get("action") or "").lower().strip()
    mapping = {
        "play": (VK_MEDIA_PLAY_PAUSE, "Playing."),
        "pause": (VK_MEDIA_PLAY_PAUSE, "Paused."),
        "play_pause": (VK_MEDIA_PLAY_PAUSE, "Toggled playback."),
        "stop": (VK_MEDIA_STOP, "Stopped media."),
        "next": (VK_MEDIA_NEXT, "Next track."),
        "previous": (VK_MEDIA_PREV, "Previous track."),
        "prev": (VK_MEDIA_PREV, "Previous track."),
    }
    if action not in mapping:
        return {"success": False, "error": f"Unknown media action: {action}"}
    try:
        vk, message = mapping[action]
        _media_key(vk)
        return {"success": True, "message": message, "action": action}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="stop",
        description="Stop current speech or action",
        parameters={},
        required=[],
        risk_level=RiskLevel.SAFE,
        execute=_stop,
    ))
    registry.register(ToolDefinition(
        name="media_control",
        description="Control media playback (play, pause, stop, next, previous)",
        parameters={
            "action": {
                "type": "string",
                "enum": ["play", "pause", "play_pause", "stop", "next", "previous"],
            }
        },
        required=["action"],
        risk_level=RiskLevel.SAFE,
        execute=_media_control,
    ))
