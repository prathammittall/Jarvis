"""System tray integration."""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.core.state import AssistantState


class JarvisTray:
    def __init__(self, assistant, window, app) -> None:
        self._assistant = assistant
        self._window = window
        self._app = app
        self._wake_enabled = True

        self.tray = QSystemTrayIcon()
        self.tray.setToolTip("JARVIS")

        menu = QMenu()
        menu.addAction("JARVIS").setEnabled(False)
        menu.addSeparator()

        self._status_action = menu.addAction("Status: Listening")
        self._status_action.setEnabled(False)

        self._toggle_wake = menu.addAction("Disable Wake Word", self._toggle_wake_word)
        menu.addAction("Open Dashboard", self._show_window)
        menu.addSeparator()
        menu.addAction("Restart", self._restart)
        menu.addAction("Exit", self._exit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _toggle_wake_word(self) -> None:
        self._wake_enabled = not self._wake_enabled
        self._assistant.toggle_wake_word(self._wake_enabled)
        label = "Enable Wake Word" if not self._wake_enabled else "Disable Wake Word"
        self._toggle_wake.setText(label)

    def _restart(self) -> None:
        self._assistant.stop()
        self._assistant.start()

    def _exit(self) -> None:
        self._assistant.stop()
        self._app.quit()

    def update_status(self, state: AssistantState) -> None:
        from app.ui.status import STATE_LABELS
        label = STATE_LABELS.get(state, "Unknown")
        self._status_action.setText(f"Status: {label}")
