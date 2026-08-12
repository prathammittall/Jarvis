"""Tests for JARVIS."""

import pytest


@pytest.fixture
def registry():
    from app.tools.registry import get_registry
    return get_registry()


class TestToolRegistry:
    def test_registry_has_tools(self, registry):
        tools = registry.list_tools()
        assert len(tools) > 0
        names = {t.name for t in tools}
        assert "open_application" in names
        assert "get_system_info" in names
        assert "take_screenshot" in names

    def test_unknown_tool(self, registry):
        result = registry.execute("nonexistent_tool", {})
        assert result["success"] is False

    def test_validate_missing_params(self, registry):
        error = registry.validate("open_application", {})
        assert error is not None

    def test_get_time(self, registry):
        result = registry.execute("get_time", {})
        assert result["success"] is True
        assert "time" in result

    def test_get_system_info_cpu(self, registry):
        result = registry.execute("get_system_info", {"type": "cpu"})
        assert result["success"] is True
        assert "cpu_percent" in result["data"]


class TestStateMachine:
    def test_initial_state(self):
        from app.core.state import AssistantState, StateMachine
        sm = StateMachine()
        assert sm.state == AssistantState.IDLE

    def test_valid_transition(self):
        from app.core.state import AssistantState, StateMachine
        sm = StateMachine()
        assert sm.transition(AssistantState.LISTENING_FOR_WAKE_WORD)
        assert sm.state == AssistantState.LISTENING_FOR_WAKE_WORD

    def test_invalid_transition(self):
        from app.core.state import AssistantState, StateMachine
        sm = StateMachine()
        assert not sm.transition(AssistantState.EXECUTING)


class TestParser:
    def test_extract_json_direct(self):
        from app.brain.parser import extract_json
        data = extract_json('{"action": "respond", "response": "Hello"}')
        assert data["action"] == "respond"

    def test_extract_json_fenced(self):
        from app.brain.parser import extract_json
        text = '```json\n{"action": "open_application", "arguments": {"application": "chrome"}}\n```'
        data = extract_json(text)
        assert data["action"] == "open_application"

    def test_is_confirmation(self):
        from app.brain.parser import is_confirmation, is_denial
        assert is_confirmation("yes")
        assert is_confirmation("do it")
        assert is_denial("no")
        assert is_denial("cancel")


class TestMemory:
    def test_store_and_recall(self):
        from app.memory.memory import MemoryManager
        mm = MemoryManager()
        mm.store("fact", "test_key", "test_value")
        result = mm.recall("test_key")
        assert result == "test_value"
        mm.forget("test_key")


class TestFilesystem:
    def test_create_and_list(self, registry, tmp_path):
        folder = tmp_path / "TestFolder"
        result = registry.execute("create_folder", {"path": str(folder)})
        assert result["success"] is True
        assert folder.is_dir()

    def test_create_file(self, registry, tmp_path):
        f = tmp_path / "notes.txt"
        result = registry.execute("create_file", {"path": str(f), "content": "hello"})
        assert result["success"] is True
        assert f.read_text() == "hello"


class TestOllama:
    def test_health_check(self):
        from app.brain.ollama_client import OllamaClient
        client = OllamaClient()
        health = client.health_check()
        assert "running" in health
        assert "models" in health
