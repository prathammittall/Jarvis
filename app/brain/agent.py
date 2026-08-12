"""JARVIS agent — fast router, then Grok, then Ollama fallback."""

from __future__ import annotations

import time
from typing import Any

from app.brain.fast_commands import get_fast_router
from app.brain.parser import ParseError, extract_json, is_confirmation, is_denial, validate_action
from app.brain.prompts import SYSTEM_PROMPT, TOOL_FILTER_KEYWORDS, TOOL_SELECTION_TEMPLATE
from app.brain.providers import get_provider_chain
from app.brain.providers.base import LLMError
from app.config import get_settings
from app.core.events import EventBus, EventType
from app.core.logger import get_logger
from app.memory.memory import MemoryManager
from app.tools.registry import RiskLevel, get_registry

logger = get_logger("agent")

ALWAYS_INCLUDE_TOOLS = {"get_time", "stop", "remember", "recall"}


class Agent:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._providers = get_provider_chain()
        self._registry = get_registry()
        self._memory = MemoryManager()
        self._events = event_bus
        self._conversation: list[dict[str, str]] = []
        self._pending_action: dict[str, Any] | None = None
        self._settings = get_settings()
        self._fast = get_fast_router()

    @property
    def ollama(self):
        """Backward-compatible access to the Ollama client."""
        return self._providers.ollama.client

    @property
    def providers(self):
        return self._providers

    def _debug(self, category: str, message: str) -> None:
        if self._events:
            self._events.debug(category, message)
        logger.debug("[%s] %s", category, message)

    def _build_context(self) -> str:
        # Limit history sent to cloud LLM
        turns = self._conversation[-(min(4, self._settings.conversation_context_turns) * 2):]
        if not turns:
            return "(none)"
        return "\n".join(f"{t['role']}: {t['content'][:200]}" for t in turns)

    def _build_memories(self) -> str:
        from app.memory.database import Database
        db = Database()
        with db._connect() as conn:
            rows = conn.execute("SELECT key, value FROM memories LIMIT 5").fetchall()
            memories = [dict(r) for r in rows]
        if not memories:
            return "(none)"
        return "\n".join(f"- {m['key']}: {m['value'][:120]}" for m in memories)

    def _filter_tools(self, command: str) -> list[dict[str, Any]]:
        all_schemas = self._registry.get_schemas()
        cmd = command.lower()
        selected: set[str] = set(ALWAYS_INCLUDE_TOOLS)
        for tool_name, keywords in TOOL_FILTER_KEYWORDS.items():
            if any(kw in cmd for kw in keywords):
                selected.add(tool_name)
        filtered = [t for t in all_schemas if t["name"] in selected]
        if len(filtered) < 3:
            return all_schemas
        return filtered

    def process_command(self, command: str) -> dict[str, Any]:
        total_start = time.perf_counter()
        command = command.strip()
        if not command:
            return {"response": "I didn't catch that.", "success": False}

        self._debug("STT", f'"{command}"')

        if self._pending_action:
            result = self._handle_confirmation(command)
            result.setdefault("timings", {})["total"] = time.perf_counter() - total_start
            self._log_perf(result.get("timings", {}))
            return result

        if any(kw in command.lower() for kw in ("stop talking", "stop.", "be quiet", "shut up")):
            from app.tools.media import _stop
            _stop({})
            return {"response": "Stopped.", "success": True, "source": "fast"}

        # 1) Fast local commands — never call Grok/Ollama
        if self._settings.fast_commands_enabled:
            fast_result = self._fast.execute(command)
            if fast_result is not None:
                if fast_result.get("awaiting_confirmation") and fast_result.get("pending_action"):
                    self._pending_action = fast_result["pending_action"]
                    if self._events:
                        self._events.emit(
                            EventType.CONFIRMATION_REQUIRED,
                            action=fast_result.get("tool"),
                            message=fast_result.get("response"),
                        )

                self._conversation.append({"role": "user", "content": command})
                self._conversation.append({"role": "assistant", "content": fast_result.get("response", "")})

                if self._events and fast_result.get("tool") and not fast_result.get("awaiting_confirmation"):
                    self._events.emit(
                        EventType.TOOL_SELECTED,
                        action=fast_result["tool"],
                        arguments=fast_result.get("arguments", {}),
                    )
                    self._events.emit(
                        EventType.TOOL_RESULT,
                        action=fast_result["tool"],
                        result=fast_result.get("result", {}),
                    )

                timings = fast_result.setdefault("timings", {})
                timings["total"] = time.perf_counter() - total_start
                self._log_perf(timings, label="FAST")
                self._debug("FAST", f"{fast_result.get('fast_command')} -> {fast_result.get('tool')}")
                return fast_result

        # 2) LLM path: Grok → Ollama
        if not self._providers.any_available():
            return {
                "response": (
                    "No LLM is available. Fast commands still work. "
                    "Set GROK_API_KEY or start Ollama for smarter requests."
                ),
                "success": False,
                "source": "none",
            }

        result = self._select_and_execute(command)
        result.setdefault("timings", {})["total"] = time.perf_counter() - total_start
        self._log_perf(result.get("timings", {}))
        return result

    def _log_perf(self, timings: dict[str, float], label: str = "LLM") -> None:
        parts = []
        for key in (
            "fast_router", "grok", "ollama", "llm",
            "tool_execution", "tts", "total",
        ):
            if key in timings:
                parts.append(f"{key}={timings[key]:.3f}s")
        if parts:
            logger.info("[PERF][%s] %s", label, " | ".join(parts))

    def _handle_confirmation(self, command: str) -> dict[str, Any]:
        if is_confirmation(command):
            action = self._pending_action
            self._pending_action = None
            if action:
                return self._execute_tool(
                    action["action"],
                    action["arguments"],
                    action.get("response", ""),
                    source=action.get("source", "llm"),
                )
            return {"response": "Confirmed.", "success": True}
        if is_denial(command):
            self._pending_action = None
            return {"response": "Cancelled.", "success": True}
        return {
            "response": "Please say yes to confirm or no to cancel.",
            "success": True,
            "awaiting_confirmation": True,
        }

    def _select_and_execute(self, command: str) -> dict[str, Any]:
        tools_desc = self._filter_tools(command)
        tools_text = "\n".join(f"- {t['name']}: {t['description']}" for t in tools_desc)

        prompt = TOOL_SELECTION_TEMPLATE.format(
            command=command,
            context=self._build_context(),
            tools=tools_text,
            memories=self._build_memories(),
        )

        self._debug("LLM", f"Selecting tool via {self._providers.primary_name()} ({len(tools_desc)} tools)...")
        start = time.perf_counter()

        try:
            chat = self._providers.chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                format_json=True,
                tools=tools_desc,
            )
        except LLMError as e:
            logger.error("LLM provider error: %s", e)
            return {
                "response": f"I couldn't reach an LLM. {e}",
                "success": False,
                "source": "none",
            }

        llm_elapsed = time.perf_counter() - start
        provider = chat.provider or "llm"
        self._debug(provider.upper(), f"Response in {chat.elapsed:.2f}s (wall {llm_elapsed:.2f}s)")

        known_tools = {t.name for t in self._registry.list_tools()} | {"respond"}

        # Prefer native tool call from Grok
        if chat.has_tool_call:
            action = chat.tool_name or "respond"
            arguments = dict(chat.tool_arguments or {})
            if action == "respond":
                response = arguments.pop("response", chat.content) or "Done."
                arguments = {}
            else:
                response = arguments.pop("response", "") if "response" in arguments else ""
                if not response:
                    response = chat.content or ""
            needs_confirmation = False
            data = {
                "action": action,
                "arguments": arguments,
                "response": response,
                "needs_confirmation": needs_confirmation,
            }
        else:
            try:
                data = extract_json(chat.content)
            except ParseError as e:
                logger.error("Agent parse error: %s", e)
                return {
                    "response": f"I encountered an error parsing the LLM response.",
                    "success": False,
                    "source": provider,
                    "timings": {provider: chat.elapsed, "llm": llm_elapsed},
                }

        action_data = validate_action(data, known_tools - {"respond"})
        action = action_data["action"]
        arguments = action_data["arguments"]
        response = action_data["response"]
        needs_confirmation = action_data["needs_confirmation"]

        self._conversation.append({"role": "user", "content": command})

        if action == "respond":
            self._conversation.append({"role": "assistant", "content": response})
            return {
                "response": response,
                "success": True,
                "source": provider,
                "timings": {provider: chat.elapsed, "llm": llm_elapsed},
            }

        tool = self._registry.get(action)
        if tool and tool.risk_level in (RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.DANGEROUS):
            needs_confirmation = True

        if needs_confirmation and self._settings.confirm_dangerous_actions:
            self._pending_action = {
                "action": action,
                "arguments": arguments,
                "response": response,
                "source": provider,
            }
            confirm_msg = response or "This action requires confirmation. Should I proceed?"
            if self._events:
                self._events.emit(EventType.CONFIRMATION_REQUIRED, action=action, message=confirm_msg)
            self._conversation.append({"role": "assistant", "content": confirm_msg})
            return {
                "response": confirm_msg,
                "success": True,
                "awaiting_confirmation": True,
                "source": provider,
                "timings": {provider: chat.elapsed, "llm": llm_elapsed},
            }

        result = self._execute_tool(action, arguments, response, source=provider)
        result.setdefault("timings", {})[provider] = chat.elapsed
        result["timings"]["llm"] = llm_elapsed
        return result

    def _execute_tool(
        self,
        action: str,
        arguments: dict,
        response: str,
        source: str = "llm",
    ) -> dict[str, Any]:
        self._debug("TOOL", f"{action}({arguments})")
        if self._events:
            self._events.emit(EventType.TOOL_SELECTED, action=action, arguments=arguments)

        start = time.perf_counter()
        result = self._registry.execute(action, arguments)
        tool_elapsed = time.perf_counter() - start
        self._debug("TOOL", "Success" if result.get("success") else f"Failed: {result.get('error')}")

        if self._events:
            self._events.emit(EventType.TOOL_RESULT, action=action, result=result)

        final_response = response or result.get("message", "")
        if not final_response:
            final_response = "Done." if result.get("success") else result.get("error", "The operation failed.")

        self._conversation.append({"role": "assistant", "content": final_response})
        try:
            if len(self._conversation) >= 2:
                self._memory._db.log_conversation("user", self._conversation[-2]["content"])
            self._memory._db.log_conversation("assistant", final_response)
        except Exception:
            pass

        return {
            "response": final_response,
            "success": result.get("success", False),
            "tool": action,
            "result": result,
            "source": source,
            "timings": {"tool_execution": tool_elapsed},
        }

    def clear_context(self) -> None:
        self._conversation.clear()
        self._pending_action = None
