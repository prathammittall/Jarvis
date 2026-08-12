"""SQLite database for long-term memory."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import get_settings


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().memory_db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL DEFAULT 'fact',
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);

                CREATE TABLE IF NOT EXISTS conversation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def store_memory(self, category: str, key: str, value: str) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM memories WHERE key = ?", (key.lower(),)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE memories SET value = ?, category = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                    (value, category, key.lower()),
                )
            else:
                conn.execute(
                    "INSERT INTO memories (category, key, value) VALUES (?, ?, ?)",
                    (category, key.lower(), value),
                )

    def get_memory(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM memories WHERE key = ?", (key.lower(),)
            ).fetchone()
            return row["value"] if row else None

    def search_memories(self, query: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category, key, value FROM memories WHERE key LIKE ? OR value LIKE ?",
                (f"%{query.lower()}%", f"%{query.lower()}%"),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_memory(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memories WHERE key = ?", (key.lower(),))

    def log_conversation(self, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversation_log (role, content) VALUES (?, ?)",
                (role, content[:500]),
            )

    def get_recent_conversations(self, limit: int = 10) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversation_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
