"""Centralized logging configuration."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.config import get_settings


def setup_logging(log_file: Path | None = None, debug: bool = False) -> logging.Logger:
    settings = get_settings()
    level = logging.DEBUG if debug else getattr(logging, settings.log_level.upper(), logging.INFO)

    log_path = log_file or settings.log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("jarvis")
    root.setLevel(level)
    root.handlers.clear()

    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_fmt = logging.Formatter(
        "[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(file_fmt)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    # pythonw has no stdout — skip console handler when detached
    if sys.stdout is not None:
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(console_fmt)
            console_handler.setLevel(level)
            root.addHandler(console_handler)
        except Exception:
            pass

    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")
