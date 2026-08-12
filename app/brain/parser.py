"""Parse and validate LLM JSON responses."""

from __future__ import annotations

import json
import re
from typing import Any


class ParseError(Exception):
    pass


def extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract from code fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find first JSON object
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ParseError(f"Could not parse JSON from: {text[:200]}")


def validate_action(data: dict[str, Any], known_tools: set[str]) -> dict[str, Any]:
    action = data.get("action", "respond")
    arguments = data.get("arguments", {})
    response = data.get("response", "")
    needs_confirmation = data.get("needs_confirmation", False)

    if not isinstance(arguments, dict):
        arguments = {}

    if action != "respond" and action not in known_tools:
        return {
            "action": "respond",
            "arguments": {},
            "response": response or f"I don't know how to handle that request.",
            "needs_confirmation": False,
        }

    return {
        "action": action,
        "arguments": arguments,
        "response": response,
        "needs_confirmation": needs_confirmation,
    }


def is_confirmation(text: str) -> bool:
    affirmatives = {"yes", "yeah", "yep", "confirm", "do it", "go ahead", "sure", "ok", "okay", "proceed"}
    return text.lower().strip().rstrip(".") in affirmatives


def is_denial(text: str) -> bool:
    negatives = {"no", "nope", "cancel", "don't", "stop", "never mind", "nevermind", "abort"}
    return text.lower().strip().rstrip(".") in negatives
