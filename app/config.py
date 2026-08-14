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

    # Ollama (offline fallback)
    ollama_enabled: bool = True
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = ""
    ollama_keep_alive: str = "-1"
    ollama_warmup_enabled: bool = True
    ollama_timeout: float = 120.0

    # Gemini / Google AI (primary cloud LLM)
    gemini_enabled: bool = True
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_timeout: float = 10.0

    # Fast commands
    fast_commands_enabled: bool = True
    commands_config: str = "config/commands.json"
    apps_config: str = "config/apps.json"
    # Comma-separated dangerous actions that skip confirmation (e.g. shutdown,restart)
    trusted_commands: str = ""
    # If false, Gemini/Ollama cannot call run_terminal_command
    allow_llm_shell: bool = False

    # Language: en | hi | hinglish (response default when detection is ambiguous)
    default_language: str = "en"

    # Whisper STT
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    # auto = multilingual detection (en/hi); or en / hi
    whisper_language: str = "auto"

    # Wake word (local only — never sent to Gemini/Ollama)
    wake_word: str = "jarvis"
    wake_word_enabled: bool = True
    wake_word_engine: str = "openwakeword"
    wake_word_threshold: float = 0.3
    wake_word_model: str = "hey_jarvis"
    listening_enabled: bool = True

    # Global hotkey (Windows-wide push-to-talk)
    global_hotkey_enabled: bool = True
    global_hotkey: str = "ctrl+space"

    # TTS
    tts_enabled: bool = True
    tts_voice: str = "en_US-lessac-medium"
    tts_voice_hi: str = "hi_IN-pratham-medium"
    tts_speed: float = 1.0

    # Audio
    microphone_index: int | None = None
    speaker_index: int | None = None
    audio_sample_rate: int = 16000
    command_max_duration: float = 8.0
    command_silence_timeout: float = 0.8

    # Assistant
    jarvis_name: str = "Jarvis"
    activation_sound: bool = True
    confirm_dangerous_actions: bool = True
    conversation_context_turns: int = 6

    # UI — default to tray (no dashboard until opened)
    ui_enabled: bool = True
    ui_always_on_top: bool = True
    ui_start_minimized: bool = True

    # Launch Jarvis when Windows signs in (also toggled from the tray)
    start_with_windows: bool = False

    # Logging
    log_level: str = "INFO"
    debug_mode: bool = False

    # Paths
    projects_config: str = "config/projects.json"
    screenshots_dir: str = "data/screenshots"
    contacts_config: str = "config/contacts.json"
    whatsapp_country_code: str = "91"

    @field_validator("microphone_index", "speaker_index", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> int | None:
        if v == "" or v is None:
            return None
        return int(v)

    @field_validator("ollama_keep_alive", mode="before")
    @classmethod
    def keep_alive_as_str(cls, v: Any) -> str:
        if v is None:
            return "-1"
        return str(v).strip()

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def gemini_key_from_aliases(cls, v: Any) -> str:
        """Accept GEMINI_API_KEY or fall back to GOOGLE_API_KEY / GOOGLE_AI_API_KEY."""
        if v:
            return str(v).strip().strip('"').strip("'")
        return (
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_AI_API_KEY")
            or ""
        ).strip().strip('"').strip("'")

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

    def trusted_command_set(self) -> set[str]:
        return {
            part.strip().lower()
            for part in (self.trusted_commands or "").split(",")
            if part.strip()
        }

    def ensure_directories(self) -> None:
        for d in (DATA_DIR, LOGS_DIR, MODELS_DIR, self.screenshots_path, self.piper_model_dir):
            d.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
