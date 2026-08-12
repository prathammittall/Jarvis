"""JARVIS agent - orchestrates LLM tool selection and execution."""

from __future__ import annotations

import time
from typing import Any

from app.brain.ollama_client import OllamaClient, OllamaError
from app.brain.parser import ParseError, extract_json, is_confirmation, is_denial, validate_action
from app.brain.prompts import CONFIRMATION_PROMPT, SYSTEM_PROMPT, TOOL_SELECTION_TEMPLATE
from app.config import get_settings
from app.core.events import EventBus, EventType
from app.core.logger import get_logger
from app.memory.memory import MemoryManager
from app.tools.registry import RiskLevel, get_registry

logger = get_logger("agent")


class Agent:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._ollama = OllamaClient()
        self._registry = get_registry()
        self._memory = MemoryManager()
        self._events = event_bus
        self._conversation: list[dict[str, str]] = []
        self._pending_action: dict[str, Any] | None = None
        self._settings = get_settings()

    @property
    def ollama(self) -> OllamaClient:
        return self._ollama

    def _debug(self, category: str, message: str) -> None:
        if self._events:
            self._events.debug(category, message)
        logger.debug("[%s] %s", category, message)

    def _build_context(self) -> str:
        turns = self._conversation[-self._settings.conversation_context_turns * 2:]
        if not turns:
            return "(none)"
        return "\n".join(f"{t['role']}: {t['content']}" for t in turns)

    def _build_memories(self) -> str:
        from app.memory.database import Database
        db = Database()
        with db._connect() as conn:
            rows = conn.execute("SELECT key, value FROM memories LIMIT 10").fetchall()
            memories = [dict(r) for r in rows]
        if not memories:
            return "(none)"
        return "\n".join(f"- {m['key']}: {m['value']}" for m in memories)

    def process_command(self, command: str) -> dict[str, Any]:
        """Process a user voice command and return result."""
        command = command.strip()
        if not command:
            return {"response": "I didn't catch that.", "success": False}

        self._debug("STT", f'"{command}"')

        # Handle pending confirmation
        if self._pending_action:
            return self._handle_confirmation(command)

        # Handle stop/interrupt
        if any(kw in command.lower() for kw in ("stop talking", "stop.", "be quiet", "shut up")):
            from app.tools.media import _stop
            _stop({})
            return {"response": "Stopped.", "success": True}

        # Check Ollama
        if not self._ollama.is_running():
            return {
                "response": "Ollama is not running. Please start Ollama and try again.",
                "success": False,
            }

        return self._select_and_execute(command)

    def _handle_confirmation(self, command: str) -> dict[str, Any]:
        if is_confirmation(command):
            action = self._pending_action
            self._pending_action = None
            if action:
                return self._execute_tool(action["action"], action["arguments"], action.get("response", ""))
            return {"response": "Confirmed.", "success": True}
        elif is_denial(command):
            self._pending_action = None
            return {"response": "Cancelled.", "success": True}
        else:
            return {"response": "Please say yes to confirm or no to cancel.", "success": True, "awaiting_confirmation": True}

    def _select_and_execute(self, command: str) -> dict[str, Any]:
        tools_desc = self._registry.get_schemas()
        tools_text = "\n".join(
            f"- {t['name']}: {t['description']} (risk: {t['risk_level']})"
            for t in tools_desc
        )

        prompt = TOOL_SELECTION_TEMPLATE.format(
            command=command,
            context=self._build_context(),
            tools=tools_text,
            memories=self._build_memories(),
        )

        self._debug("OLLAMA", "Selecting tool...")
        start = time.perf_counter()

        try:
            raw = self._ollama.chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format_json=True,
            )
            self._debug("OLLAMA", f"Response in {time.perf_counter() - start:.2f}s")
            data = extract_json(raw)
        except (OllamaError, ParseError) as e:
            logger.error("Agent error: %s", e)
            return {"response": f"I encountered an error: {e}", "success": False}

        known_tools = {t.name for t in self._registry.list_tools()}
        action_data = validate_action(data, known_tools)

        action = action_data["action"]
        arguments = action_data["arguments"]
        response = action_data["response"]
        needs_confirmation = action_data["needs_confirmation"]

        self._conversation.append({"role": "user", "content": command})

        if action == "respond":
            self._conversation.append({"role": "assistant", "content": response})
            return {"response": response, "success": True}

        # Check tool risk level
        tool = self._registry.get(action)
        if tool and tool.risk_level in (RiskLevel.CONFIRMATION_REQUIRED, RiskLevel.DANGEROUS):
            needs_confirmation = True

        if needs_confirmation and self._settings.confirm_dangerous_actions:
            self._pending_action = {"action": action, "arguments": arguments, "response": response}
            confirm_msg = response or f"This action requires confirmation. Should I proceed?"
            if self._events:
                self._events.emit(EventType.CONFIRMATION_REQUIRED, action=action, message=confirm_msg)
            self._conversation.append({"role": "assistant", "content": confirm_msg})
            return {"response": confirm_msg, "success": True, "awaiting_confirmation": True}

        return self._execute_tool(action, arguments, response)

    def _execute_tool(self, action: str, arguments: dict, response: str) -> dict[str, Any]:
        self._debug("TOOL", f"{action}({arguments})")
        if self._events:
            self._events.emit(EventType.TOOL_SELECTED, action=action, arguments=arguments)

        result = self._registry.execute(action, arguments)
        self._debug("TOOL", "Success" if result.get("success") else f"Failed: {result.get('error')}")

        if self._events:
            self._events.emit(EventType.TOOL_RESULT, action=action, result=result)

        final_response = response or result.get("message", "")
        if not final_response:
            if result.get("success"):
                final_response = "Done."
            else:
                final_response = result.get("error", "The operation failed.")

        self._conversation.append({"role": "assistant", "content": final_response})
        self._memory._db.log_conversation("user", self._conversation[-2]["content"] if len(self._conversation) >= 2 else "")
        self._memory._db.log_conversation("assistant", final_response)

        return {
            "response": final_response,
            "success": result.get("success", False),
            "tool": action,
            "result": result,
        }

    def clear_context(self) -> None:
        self._conversation.clear()
        self._pending_action = None
