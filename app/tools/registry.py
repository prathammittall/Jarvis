"""Tool registry with validation and execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class RiskLevel(Enum):
    SAFE = "safe"
    CONFIRMATION_REQUIRED = "confirmation_required"
    DANGEROUS = "dangerous"


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    risk_level: RiskLevel
    execute: Callable[[dict[str, Any]], dict[str, Any]]
    required: list[str] = field(default_factory=list)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "risk_level": t.risk_level.value,
            }
            for t in self._tools.values()
        ]

    def validate(self, name: str, arguments: dict[str, Any]) -> str | None:
        tool = self.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        for req in tool.required:
            if req not in arguments or arguments[req] is None:
                return f"Missing required parameter: {req}"
        return None

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        if tool is None:
            return {"success": False, "error": f"Unknown tool: {name}"}
        error = self.validate(name, arguments)
        if error:
            return {"success": False, "error": error}
        try:
            return tool.execute(arguments)
        except Exception as e:
            return {"success": False, "error": str(e)}


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_all(_registry)
    return _registry


def _register_all(registry: ToolRegistry) -> None:
    from app.tools import (
        applications, browser, filesystem, media,
        memory_tools, system_info, terminal, web, windows_tools, whatsapp,
    )
    for module in (
        applications, browser, filesystem, media,
        memory_tools, system_info, terminal, web, windows_tools, whatsapp,
    ):
        module.register(registry)
