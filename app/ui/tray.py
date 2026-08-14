"""System tray integration — stays responsive while AI / TTS / actions run."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from app.core.logger import get_logger
from app.core.state import AssistantState

logger = get_logger("tray")


def jarvis_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2ee6a6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor("#0b1220"))
    font = QFont("Segoe UI", 22, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "J")
    painter.end()
    return QIcon(pix)


class JarvisTray(QObject):
    mic_finished = Signal(str)
    sig_state = Signal(object)

    def __init__(self, assistant, window, app: QApplication) -> None:
        super().__init__()
        self._assistant = assistant
        self._window = window
        self._app = app
        self._settings_dialog = None

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(jarvis_icon())
        self.tray.setToolTip("Jarvis")
        app.setWindowIcon(jarvis_icon())

        menu = QMenu()
        header = menu.addAction("Jarvis")
        header.setEnabled(False)
        menu.addSeparator()

        self._status_action = menu.addAction("Status: Listening")
        self._status_action.setEnabled(False)
        menu.addSeparator()

        self._enable_action = QAction("🎙 Enable Listening", menu)
        self._enable_action.triggered.connect(self._enable_listening)
        menu.addAction(self._enable_action)

        self._pause_action = QAction("⏸ Pause Listening", menu)
        self._pause_action.triggered.connect(self._pause_listening)
        menu.addAction(self._pause_action)

        menu.addSeparator()
        menu.addAction("⌨ Test Microphone", self._test_microphone)
        menu.addAction("⚙ Settings", self._open_settings)
        menu.addAction("Open Dashboard", self._show_window)
        menu.addSeparator()
        menu.addAction("🔄 Restart Jarvis", self._restart)
        menu.addAction("❌ Exit", self._exit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.mic_finished.connect(self._show_mic_result)
        self.sig_state.connect(self.update_status)
        self.tray.show()
        self._sync_listening_actions()

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _enable_listening(self) -> None:
        self._assistant.set_listening_enabled(True)
        self._sync_listening_actions()
        self.tray.showMessage("Jarvis", "Listening enabled", QSystemTrayIcon.MessageIcon.Information, 1500)

    def _pause_listening(self) -> None:
        self._assistant.set_listening_enabled(False)
        self._sync_listening_actions()
        self.tray.showMessage("Jarvis", "Listening paused", QSystemTrayIcon.MessageIcon.Information, 1500)

    def _sync_listening_actions(self) -> None:
        listening = self._assistant.is_listening()
        self._enable_action.setEnabled(not listening)
        self._pause_action.setEnabled(listening)

    def _test_microphone(self) -> None:
        was_listening = self._assistant.is_listening()
        self._assistant.set_listening_enabled(False)

        def _run():
            from app.speech.mic_test import test_microphone
            result = test_microphone(2.0)
            if was_listening:
                self._assistant.set_listening_enabled(True)
            self.mic_finished.emit(result["message"])

        self.tray.showMessage("Jarvis", "Speak now — testing microphone…", QSystemTrayIcon.MessageIcon.Information, 1500)
        threading.Thread(target=_run, daemon=True, name="mic-test").start()

    def _show_mic_result(self, message: str) -> None:
        self._sync_listening_actions()
        QMessageBox.information(self._window, "Microphone", message)

    def _open_settings(self) -> None:
        from app.ui.settings import SettingsDialog
        dlg = SettingsDialog(self._assistant, parent=self._window)
        dlg.exec()
        self._sync_listening_actions()

    def _restart(self) -> None:
        logger.info("Restart requested from tray")
        self._assistant.restart()
        self._sync_listening_actions()

    def _exit(self) -> None:
        logger.info("Exit requested from tray")
        try:
            self._assistant.stop()
        except Exception:
            pass
        self.tray.hide()
        self._app.quit()

    def update_status(self, state: AssistantState) -> None:
        from app.ui.status import STATE_LABELS
        label = STATE_LABELS.get(state, "Unknown")
        self._status_action.setText(f"Status: {label}")
        self.tray.setToolTip(f"Jarvis — {label}")
        self._sync_listening_actions()
