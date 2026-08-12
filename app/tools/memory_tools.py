"""Long-term memory tools."""

from __future__ import annotations

from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition


def _remember(args: dict[str, Any]) -> dict[str, Any]:
    from app.memory.memory import MemoryManager
    key = args.get("key", "")
    value = args.get("value", "")
    category = args.get("category", "fact")
    if not key or not value:
        return {"success": False, "error": "Key and value required."}
    MemoryManager().store(category, key, value)
    return {"success": True, "message": f"I'll remember that {key} is {value}."}


def _forget(args: dict[str, Any]) -> dict[str, Any]:
    from app.memory.memory import MemoryManager
    key = args.get("key", "")
    MemoryManager().forget(key)
    return {"success": True, "message": f"Forgotten: {key}."}


def _recall(args: dict[str, Any]) -> dict[str, Any]:
    from app.memory.memory import MemoryManager
    query = args.get("query", "")
    results = MemoryManager().search(query)
    if not results:
        return {"success": True, "message": "I don't have anything stored about that.", "results": []}
    items = [f"{r['key']}: {r['value']}" for r in results]
    return {"success": True, "message": ". ".join(items), "results": results}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="remember", description="Store a fact or preference in long-term memory",
        parameters={
            "key": {"type": "string"}, "value": {"type": "string"},
            "category": {"type": "string", "description": "fact, preference, or project"},
        },
        required=["key", "value"], risk_level=RiskLevel.SAFE, execute=_remember,
    ))
    registry.register(ToolDefinition(
        name="forget", description="Remove a stored memory",
        parameters={"key": {"type": "string"}}, required=["key"],
        risk_level=RiskLevel.SAFE, execute=_forget,
    ))
    registry.register(ToolDefinition(
        name="recall", description="Recall stored memories about a topic",
        parameters={"query": {"type": "string"}}, required=["query"],
        risk_level=RiskLevel.SAFE, execute=_recall,
    ))
