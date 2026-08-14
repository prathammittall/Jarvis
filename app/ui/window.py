"""JARVIS main dashboard window."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget,
)

from app.core.state import AssistantState
from app.ui.status import (
    STATE_COLORS, STATE_HINTS, STATE_LABELS, STATE_MESSAGES, VOICE_INPUT_STATES,
)
from app.ui.widgets import VoiceOrb, WaveformBar


class JarvisWindow(QMainWindow):
    """Compact always-on-top dashboard with live voice feedback."""

    # Thread-safe signals (emit from any thread; slots run on UI thread)
    sig_state = Signal(object)
    sig_command = Signal(str)
    sig_response = Signal(str)
    sig_activity = Signal(str)
    sig_level = Signal(float)
    sig_tool = Signal(str)
    talk_requested = Signal()

    def __init__(self, always_on_top: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS")
        self.setFixedSize(380, 560)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._drag_pos: QPoint | None = None
        self._state = AssistantState.IDLE
        self._ellipsis_step = 0

        self._setup_ui()
        self._setup_style()
        self._wire_signals()

        self._ellipsis_timer = QTimer(self)
        self._ellipsis_timer.timeout.connect(self._animate_ellipsis)
        self._ellipsis_timer.start(450)

    def _setup_ui(self) -> None:
        shell = QWidget()
        self.setCentralWidget(shell)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        shell_layout.addWidget(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setSpacing(10)
        layout.setContentsMargins(22, 18, 22, 20)

        # Header
        header = QHBoxLayout()
        self.brand = QLabel("JARVIS")
        self.brand.setObjectName("brand")
        self.brand.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.badge = QLabel("ONLINE")
        self.badge.setObjectName("badge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(self.brand)
        header.addStretch()
        header.addWidget(self.badge)

        self.close_btn = QLabel("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Hide to tray")
        self.close_btn.mousePressEvent = self._hide_to_tray  # type: ignore[method-assign]
        header.addWidget(self.close_btn)
        layout.addLayout(header)

        # Divider
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # Orb (click to talk)
        orb_wrap = QHBoxLayout()
        orb_wrap.addStretch()
        self.orb = VoiceOrb()
        self.orb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.orb.setToolTip("Click to talk")
        self.orb.mousePressEvent = self._on_orb_clicked  # type: ignore[method-assign]
        orb_wrap.addWidget(self.orb)
        orb_wrap.addStretch()
        layout.addLayout(orb_wrap)

        # Primary status
        self.status_label = QLabel("Standing by")
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Hint / secondary line
        self.hint_label = QLabel("Systems initializing")
        self.hint_label.setObjectName("hint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        # Live waveform
        self.wave = WaveformBar()
        layout.addWidget(self.wave)

        # Receiving banner
        self.recv_label = QLabel("")
        self.recv_label.setObjectName("recv")
        self.recv_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recv_label.setVisible(False)
        layout.addWidget(self.recv_label)

        # Command card
        self.cmd_card = QFrame()
        self.cmd_card.setObjectName("cmdCard")
        cmd_layout = QVBoxLayout(self.cmd_card)
        cmd_layout.setContentsMargins(12, 10, 12, 10)
        cmd_layout.setSpacing(4)

        self.cmd_caption = QLabel("LAST COMMAND")
        self.cmd_caption.setObjectName("caption")
        self.cmd_text = QLabel("Waiting for voice input")
        self.cmd_text.setObjectName("cmdText")
        self.cmd_text.setWordWrap(True)
        cmd_layout.addWidget(self.cmd_caption)
        cmd_layout.addWidget(self.cmd_text)
        layout.addWidget(self.cmd_card)

        # Response card
        self.resp_card = QFrame()
        self.resp_card.setObjectName("respCard")
        resp_layout = QVBoxLayout(self.resp_card)
        resp_layout.setContentsMargins(12, 10, 12, 10)
        resp_layout.setSpacing(4)

        self.resp_caption = QLabel("RESPONSE")
        self.resp_caption.setObjectName("caption")
        self.resp_text = QLabel("—")
        self.resp_text.setObjectName("respText")
        self.resp_text.setWordWrap(True)
        resp_layout.addWidget(self.resp_caption)
        resp_layout.addWidget(self.resp_text)
        layout.addWidget(self.resp_card)

        # Activity footer
        self.activity = QLabel("Ready")
        self.activity.setObjectName("activity")
        self.activity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity.setWordWrap(True)
        layout.addWidget(self.activity)

        # Click-to-talk button (reliable fallback if wake word fails)
        from PySide6.QtWidgets import QPushButton
        self.talk_btn = QPushButton("Click to Talk  ·  or say Jarvis  ·  Space")
        self.talk_btn.setObjectName("talkBtn")
        self.talk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.talk_btn.setToolTip("Activate listening (also Spacebar, or say Jarvis)")
        self.talk_btn.clicked.connect(self.talk_requested.emit)
        layout.addWidget(self.talk_btn)

    def _setup_style(self) -> None:
        families = QFontDatabase.families()
        brand_font = "Orbitron" if "Orbitron" in families else (
            "Bahnschrift" if "Bahnschrift" in families else "Segoe UI"
        )
        body_font = "Cascadia Mono" if "Cascadia Mono" in families else (
            "Consolas" if "Consolas" in families else "Segoe UI"
        )

        self.brand.setFont(QFont(brand_font, 18, QFont.Weight.Bold))
        self.status_label.setFont(QFont("Segoe UI Semibold", 13))
        self.hint_label.setFont(QFont(body_font, 9))
        self.cmd_text.setFont(QFont("Segoe UI", 10))
        self.resp_text.setFont(QFont("Segoe UI", 10))
        self.activity.setFont(QFont(body_font, 8))

        self.setStyleSheet("""
            #panel {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0b1220,
                    stop:0.55 #0a101a,
                    stop:1 #070b14
                );
                border: 1px solid #1c2a3d;
                border-radius: 18px;
            }
            #brand {
                color: #e8f1ff;
                letter-spacing: 4px;
            }
            #badge {
                color: #0b1220;
                background: #2ee6a6;
                border-radius: 8px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 700;
            }
            #divider {
                background: #1a2738;
                border: none;
            }
            #status {
                color: #f0f6ff;
                padding: 2px 8px;
            }
            #hint {
                color: #7f93ab;
                padding: 0 8px;
            }
            #recv {
                color: #ffb020;
                background: rgba(255, 176, 32, 0.12);
                border: 1px solid rgba(255, 176, 32, 0.35);
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            #cmdCard, #respCard {
                background: rgba(18, 28, 44, 0.9);
                border: 1px solid #223246;
                border-radius: 12px;
            }
            #caption {
                color: #5f738a;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            #cmdText {
                color: #c9daf0;
            }
            #respText {
                color: #9ec8ff;
            }
            #activity {
                color: #5a6f86;
                padding-top: 4px;
            }
            #closeBtn {
                color: #6b7f95;
                font-size: 12px;
                padding: 2px 6px;
                margin-left: 6px;
            }
            #closeBtn:hover {
                color: #ff6b8a;
            }
            #talkBtn {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a6bff, stop:1 #2ee6a6
                );
                color: #061018;
                border: none;
                border-radius: 12px;
                padding: 12px;
                font-size: 13px;
                font-weight: 700;
            }
            #talkBtn:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3a82ff, stop:1 #4af0b8
                );
            }
            #talkBtn:pressed {
                background: #148a6a;
            }
        """)

    def _hide_to_tray(self, event=None) -> None:
        self.hide()

    def _on_orb_clicked(self, event=None) -> None:
        self.talk_requested.emit()
        if event is not None:
            event.accept()

    def _wire_signals(self) -> None:
        self.sig_state.connect(self.update_state)
        self.sig_command.connect(self.update_command)
        self.sig_response.connect(self.update_response)
        self.sig_activity.connect(self.update_activity)
        self.sig_level.connect(self.update_level)
        self.sig_tool.connect(self.update_tool)

    def update_state(self, state: AssistantState) -> None:
        self._state = state
        color = STATE_COLORS.get(state, "#5a6a7a")
        label = STATE_LABELS.get(state, "Unknown")
        message = STATE_MESSAGES.get(state, label)
        hint = STATE_HINTS.get(state, "")

        self.orb.set_state(state)
        self.wave.set_color(color)
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")
        self.hint_label.setText(hint)

        receiving = state in VOICE_INPUT_STATES
        self.wave.set_active(receiving)
        self.recv_label.setVisible(receiving)
        if receiving:
            self.recv_label.setText("●  Receiving voice command")
            self.cmd_caption.setText("HEARING YOU")
            if state == AssistantState.LISTENING_FOR_COMMAND:
                self.cmd_text.setText("Listening… speak your command")
        else:
            self.cmd_caption.setText("LAST COMMAND")

        if state == AssistantState.ERROR:
            self.badge.setText("ERROR")
            self.badge.setStyleSheet(
                "background:#ff4d6d; color:#fff; border-radius:8px; padding:3px 10px;"
            )
        elif state == AssistantState.STOPPED:
            self.badge.setText("OFFLINE")
            self.badge.setStyleSheet(
                "background:#6b7785; color:#0b1220; border-radius:8px; padding:3px 10px;"
            )
        elif receiving:
            self.badge.setText("MIC LIVE")
            self.badge.setStyleSheet(
                "background:#ffb020; color:#0b1220; border-radius:8px; padding:3px 10px;"
            )
        elif state == AssistantState.SPEAKING:
            self.badge.setText("SPEAKING")
            self.badge.setStyleSheet(
                "background:#4da3ff; color:#0b1220; border-radius:8px; padding:3px 10px;"
            )
        elif state in (
            AssistantState.THINKING,
            AssistantState.TRANSCRIBING,
            AssistantState.EXECUTING,
        ):
            self.badge.setText(label.upper())
            self.badge.setStyleSheet(
                f"background:{color}; color:#0b1220; border-radius:8px; padding:3px 10px;"
            )
        else:
            self.badge.setText("ONLINE")
            self.badge.setStyleSheet(
                "background:#2ee6a6; color:#0b1220; border-radius:8px; padding:3px 10px;"
            )

        self.update_activity(f"State · {label}")

    def update_command(self, text: str) -> None:
        if text:
            self.cmd_caption.setText("LAST COMMAND")
            self.cmd_text.setText(f'"{text}"')
            self.update_activity("Command captured")
        else:
            self.cmd_text.setText("Waiting for voice input")

    def update_response(self, text: str) -> None:
        self.resp_text.setText(text if text else "—")

    def update_activity(self, text: str) -> None:
        self.activity.setText(text)

    def update_level(self, level: float) -> None:
        self.orb.set_level(level)
        self.wave.set_level(level)
        if self._state in VOICE_INPUT_STATES:
            pct = int(min(100, level * 100))
            if level > 0.05:
                self.recv_label.setText(f"●  Receiving voice command  ·  level {pct}%")
            else:
                self.recv_label.setText("●  Receiving voice command  ·  waiting for speech")

    def update_tool(self, name: str) -> None:
        if name:
            self.update_activity(f"Tool · {name}")
            self.hint_label.setText(f"Executing: {name}")

    def _animate_ellipsis(self) -> None:
        if self._state not in (
            AssistantState.LISTENING_FOR_COMMAND,
            AssistantState.TRANSCRIBING,
            AssistantState.THINKING,
            AssistantState.EXECUTING,
            AssistantState.SPEAKING,
            AssistantState.LISTENING_FOR_WAKE_WORD,
        ):
            return
        self._ellipsis_step = (self._ellipsis_step + 1) % 4
        dots = "." * self._ellipsis_step
        base = STATE_MESSAGES.get(self._state, "").rstrip(".…")
        self.status_label.setText(f"{base}{dots}")

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_pos = None

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_Space:
            self.talk_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
