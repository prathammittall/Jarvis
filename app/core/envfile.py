"""Safely update keys in the project .env without touching other values or secrets."""

from __future__ import annotations

from pathlib import Path

from app.config import PROJECT_ROOT


def env_path() -> Path:
    return PROJECT_ROOT / ".env"


def set_env_values(updates: dict[str, str]) -> None:
    path = env_path()
    if path.exists():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if text.endswith("\n"):
            trailing_newline = True
        else:
            trailing_newline = False
    else:
        lines = []
        trailing_newline = True

    remaining = dict(updates)
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining.pop(key)}")
        else:
            new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")

    body = "\n".join(new_lines)
    if trailing_newline or body:
        body += "\n"
    path.write_text(body, encoding="utf-8")
