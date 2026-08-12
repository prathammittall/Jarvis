"""Memory manager for preferences, projects, and facts."""

from __future__ import annotations

from app.memory.database import Database


class MemoryManager:
    _instance: "MemoryManager | None" = None

    def __new__(cls) -> "MemoryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db = Database()
        return cls._instance

    def store(self, category: str, key: str, value: str) -> None:
        self._db.store_memory(category, key, value)

    def recall(self, key: str) -> str | None:
        return self._db.get_memory(key)

    def search(self, query: str) -> list[dict]:
        return self._db.search_memories(query)

    def forget(self, key: str) -> None:
        self._db.delete_memory(key)

    def get_context(self, limit: int = 5) -> list[dict]:
        return self._db.get_recent_conversations(limit)
