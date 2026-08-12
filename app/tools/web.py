"""Web search tools."""

from __future__ import annotations

import webbrowser
from typing import Any
from urllib.parse import quote_plus

from app.tools.registry import RiskLevel, ToolDefinition


def _web_search(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "")
    engine = args.get("engine", "google").lower()
    if engine == "youtube":
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    else:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
    webbrowser.open(url)
    return {"success": True, "message": f"Searching for {query}.", "url": url}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="web_search", description="Search the web (Google or YouTube)",
        parameters={
            "query": {"type": "string"},
            "engine": {"type": "string", "description": "google or youtube"},
        },
        required=["query"], risk_level=RiskLevel.SAFE, execute=_web_search,
    ))
