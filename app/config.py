"""Application configuration loaded from environment and .env file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
MODELS_DIR = PROJECT_ROOT / "models"
CONFIG_DIR = PROJECT_ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = ""

    # Whisper STT
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    # Wake word
    wake_word_enabled: bool = True
    wake_word_engine: str = "openwakeword"
    wake_word_threshold: float = 0.5
    wake_word_model: str = "hey_jarvis"

    # TTS
    tts_enabled: bool = True
    tts_voice: str = "en_US-lessac-medium"
    tts_speed: float = 1.0

    # Audio
    microphone_index: int | None = None
    speaker_index: int | None = None
    audio_sample_rate: int = 16000
    command_max_duration: float = 15.0
    command_silence_timeout: float = 1.5

    # Assistant
    jarvis_name: str = "Jarvis"
    activation_sound: bool = True
    confirm_dangerous_actions: bool = True
    conversation_context_turns: int = 6

    # UI
    ui_enabled: bool = True
    ui_always_on_top: bool = True
    ui_start_minimized: bool = False

    # Logging
    log_level: str = "INFO"
    debug_mode: bool = False

    # Paths
    projects_config: str = "config/projects.json"
    screenshots_dir: str = "data/screenshots"

    @field_validator("microphone_index", "speaker_index", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> int | None:
        if v == "" or v is None:
            return None
        return int(v)

    @property
    def projects_path(self) -> Path:
        return PROJECT_ROOT / self.projects_config

    @property
    def screenshots_path(self) -> Path:
        return PROJECT_ROOT / self.screenshots_dir

    @property
    def memory_db_path(self) -> Path:
        return DATA_DIR / "memory.db"

    @property
    def log_file(self) -> Path:
        return LOGS_DIR / "jarvis.log"

    @property
    def piper_model_dir(self) -> Path:
        return MODELS_DIR / "piper"

    def load_projects(self) -> dict[str, str]:
        path = self.projects_path
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return {k.lower(): v for k, v in data.items()}
        except (json.JSONDecodeError, OSError):
            return {}

    def ensure_directories(self) -> None:
        for d in (DATA_DIR, LOGS_DIR, MODELS_DIR, self.screenshots_path, self.piper_model_dir):
            d.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
