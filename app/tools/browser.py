"""Browser automation with Playwright."""

from __future__ import annotations

import webbrowser
from typing import Any
from urllib.parse import quote_plus

from app.tools.registry import RiskLevel, ToolDefinition

_browser = None


def _get_browser():
    global _browser
    if _browser is None:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        _browser = pw.chromium.launch(headless=False)
    return _browser


def _open_url(args: dict[str, Any]) -> dict[str, Any]:
    url = args.get("url", "")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return {"success": True, "message": f"Opening {url}.", "url": url}


def _google_search(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "")
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    webbrowser.open(url)
    return {"success": True, "message": f"Searching Google for {query}.", "url": url}


def _youtube_search(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "")
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    webbrowser.open(url)
    return {"success": True, "message": f"Searching YouTube for {query}.", "url": url}


def _open_youtube(args: dict[str, Any]) -> dict[str, Any]:
    webbrowser.open("https://www.youtube.com")
    return {"success": True, "message": "Opening YouTube."}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="open_url", description="Open a URL in the default browser",
        parameters={"url": {"type": "string"}}, required=["url"],
        risk_level=RiskLevel.SAFE, execute=_open_url,
    ))
    registry.register(ToolDefinition(
        name="google_search", description="Search Google for a query",
        parameters={"query": {"type": "string"}}, required=["query"],
        risk_level=RiskLevel.SAFE, execute=_google_search,
    ))
    registry.register(ToolDefinition(
        name="youtube_search", description="Search YouTube for a query",
        parameters={"query": {"type": "string"}}, required=["query"],
        risk_level=RiskLevel.SAFE, execute=_youtube_search,
    ))
    registry.register(ToolDefinition(
        name="open_youtube", description="Open YouTube in the browser",
        parameters={}, required=[], risk_level=RiskLevel.SAFE, execute=_open_youtube,
    ))
