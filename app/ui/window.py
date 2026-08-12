"""JARVIS main window UI."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget,
)

from app.core.state import AssistantState
from app.ui.status import STATE_COLORS, STATE_ICONS, STATE_LABELS


class JarvisWindow(QMainWindow):
    state_changed = Signal(object, object)
    status_text_changed = Signal(str)

    def __init__(self, always_on_top: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.setFixedSize(320, 280)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint if always_on_top else Qt.WindowType.Window
        )

        self._setup_ui()
        self._setup_style()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.title_label = QLabel("J A R V I S")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        self.icon_label = QLabel("◉")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont("Segoe UI", 48))

        self.status_label = QLabel("Listening...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 11))

        self.command_label = QLabel("")
        self.command_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.command_label.setFont(QFont("Segoe UI", 9))
        self.command_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.icon_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.command_label)
        layout.addStretch()

        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start(1000)
        self._pulse_on = True

    def _setup_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0a0e17;
                color: #c8d6e5;
            }
            QLabel {
                color: #c8d6e5;
            }
        """)

    def update_state(self, state: AssistantState) -> None:
        label = STATE_LABELS.get(state, "Unknown")
        color = STATE_COLORS.get(state, "#666")
        icon = STATE_ICONS.get(state, "·")

        self.status_label.setText(f"{label}...")
        self.status_label.setStyleSheet(f"color: {color};")
        self.icon_label.setText(icon)
        self.icon_label.setStyleSheet(f"color: {color};")

    def update_command(self, text: str) -> None:
        if text:
            self.command_label.setText(f'"{text}"')
            self.command_label.setStyleSheet("color: #8899aa;")
        else:
            self.command_label.setText("")

    def _pulse(self) -> None:
        self._pulse_on = not self._pulse_on
