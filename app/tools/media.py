"""Media and interruption tools."""

from __future__ import annotations

from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition


def _stop(args: dict[str, Any]) -> dict[str, Any]:
    from app.speech.tts import TextToSpeech
    tts = TextToSpeech()
    tts.stop()
    return {"success": True, "message": "Stopped.", "action": "stop"}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="stop", description="Stop current speech or action",
        parameters={}, required=[], risk_level=RiskLevel.SAFE, execute=_stop,
    ))
