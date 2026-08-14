"""Settings dialog for listening, startup, and status."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.config import get_settings
from app.core.envfile import set_env_values
from app.core.logger import get_logger
from app.core import startup as win_startup

logger = get_logger("settings")


class SettingsDialog(QDialog):
    def __init__(self, assistant, parent=None) -> None:
        super().__init__(parent)
        self._assistant = assistant
        self.setWindowTitle("Jarvis Settings")
        self.setModal(True)
        self.setMinimumWidth(420)

        settings = get_settings()
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._listen = QCheckBox("Enable wake-word listening")
        self._listen.setChecked(assistant.is_listening())
        form.addRow("Listening", self._listen)

        self._startup = QCheckBox("Start Jarvis when Windows starts")
        self._startup.setChecked(win_startup.is_enabled() or settings.start_with_windows)
        form.addRow("Startup", self._startup)

        self._hotkey = QLabel(settings.global_hotkey or "ctrl+space")
        form.addRow("Global hotkey", self._hotkey)

        gemini = "configured" if settings.gemini_enabled and settings.gemini_api_key else "not configured"
        ollama = "enabled" if settings.ollama_enabled else "disabled"
        self._ai = QLabel(f"Gemini {gemini} · Ollama {ollama}")
        self._ai.setWordWrap(True)
        form.addRow("AI", self._ai)

        layout.addLayout(form)

        hint = QLabel(
            "API keys stay in your .env file and are never shown here. "
            "Change GEMINI_API_KEY there if needed."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        layout.addWidget(hint)

        row = QHBoxLayout()
        mic_btn = QPushButton("Test Microphone")
        mic_btn.clicked.connect(self._test_mic)
        row.addWidget(mic_btn)
        row.addStretch()
        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _test_mic(self) -> None:
        from app.speech.mic_test import test_microphone

        self._assistant.set_listening_enabled(False)
        QMessageBox.information(self, "Microphone", "Recording for 2 seconds — speak now.")
        result = test_microphone(2.0)
        if self._listen.isChecked():
            self._assistant.set_listening_enabled(True)
        QMessageBox.information(self, "Microphone", result["message"])

    def _save(self) -> None:
        listening = self._listen.isChecked()
        start_win = self._startup.isChecked()
        self._assistant.set_listening_enabled(listening)
        try:
            win_startup.set_enabled(start_win)
        except Exception as e:
            logger.error("Startup toggle failed: %s", e)
            QMessageBox.warning(self, "Startup", f"Could not update Windows startup: {e}")
        try:
            set_env_values({
                "LISTENING_ENABLED": "true" if listening else "false",
                "START_WITH_WINDOWS": "true" if start_win else "false",
                "UI_START_MINIMIZED": "true",
            })
        except Exception as e:
            logger.warning("Could not write .env: %s", e)
        logger.info("Settings saved (listening=%s, startup=%s)", listening, start_win)
        self.accept()
