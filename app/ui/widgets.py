"""Animated voice visualizer and orb for the JARVIS dashboard."""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from app.core.state import AssistantState
from app.ui.status import STATE_COLORS, VOICE_INPUT_STATES


class VoiceOrb(QWidget):
    """Central animated orb that reacts to state and microphone level."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self._state = AssistantState.IDLE
        self._level = 0.0
        self._display_level = 0.0
        self._phase = 0.0
        self._ring_phase = 0.0
        self._bars = [0.15] * 28
        self._color = QColor(STATE_COLORS[AssistantState.IDLE])

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 FPS

    def set_state(self, state: AssistantState) -> None:
        self._state = state
        self._color = QColor(STATE_COLORS.get(state, "#5a6a7a"))

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))

    def _tick(self) -> None:
        self._phase += 0.08
        self._ring_phase += 0.04
        # Smooth audio level
        self._display_level += (self._level - self._display_level) * 0.35

        active = self._state in VOICE_INPUT_STATES
        speaking = self._state == AssistantState.SPEAKING
        thinking = self._state in (
            AssistantState.THINKING,
            AssistantState.TRANSCRIBING,
            AssistantState.EXECUTING,
        )

        for i in range(len(self._bars)):
            if active:
                target = 0.2 + self._display_level * 0.75 + random.uniform(-0.08, 0.08)
            elif speaking:
                target = 0.25 + abs(math.sin(self._phase * 2 + i * 0.35)) * 0.55
            elif thinking:
                target = 0.18 + abs(math.sin(self._phase * 1.5 + i * 0.4)) * 0.35
            else:
                # Soft idle breathing
                target = 0.12 + abs(math.sin(self._phase * 0.6 + i * 0.2)) * 0.12
            self._bars[i] += (max(0.08, min(1.0, target)) - self._bars[i]) * 0.3

        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        base_r = 42 + self._display_level * 18

        # Outer glow
        glow = QRadialGradient(cx, cy, 100)
        c = QColor(self._color)
        c.setAlpha(55 if self._state in VOICE_INPUT_STATES else 30)
        glow.setColorAt(0.0, c)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 100, 100)

        # Rotating rings
        for i, radius in enumerate((78, 92, 106)):
            pen = QPen(self._color)
            pen.setWidthF(1.2 if i == 0 else 0.8)
            alpha = 140 - i * 35
            if self._state in VOICE_INPUT_STATES:
                alpha += 40
            ring_c = QColor(self._color)
            ring_c.setAlpha(max(40, alpha))
            pen.setColor(ring_c)
            if i > 0:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            start = int((self._ring_phase * 40 + i * 50) % 360 * 16)
            span = int((120 + self._display_level * 80) * 16)
            painter.drawArc(
                int(cx - radius), int(cy - radius),
                int(radius * 2), int(radius * 2),
                start, span,
            )

        # Waveform bars around orb
        n = len(self._bars)
        for i, h in enumerate(self._bars):
            angle = (i / n) * math.tau + self._phase * 0.15
            inner = base_r + 8
            outer = inner + 10 + h * 28
            x1 = cx + math.cos(angle) * inner
            y1 = cy + math.sin(angle) * inner
            x2 = cx + math.cos(angle) * outer
            y2 = cy + math.sin(angle) * outer
            bar_c = QColor(self._color)
            bar_c.setAlpha(int(90 + h * 140))
            pen = QPen(bar_c, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Core orb
        core = QRadialGradient(cx - 8, cy - 10, base_r)
        core_top = QColor(self._color).lighter(140)
        core_top.setAlpha(230)
        core_bot = QColor(self._color).darker(140)
        core_bot.setAlpha(200)
        core.setColorAt(0.0, core_top)
        core.setColorAt(0.55, QColor(self._color))
        core.setColorAt(1.0, core_bot)
        painter.setBrush(core)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), base_r, base_r)

        # Inner highlight
        hi = QRadialGradient(cx - 10, cy - 14, base_r * 0.55)
        hi.setColorAt(0.0, QColor(255, 255, 255, 70))
        hi.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(hi)
        painter.drawEllipse(QPointF(cx, cy), base_r * 0.85, base_r * 0.85)


class WaveformBar(QWidget):
    """Horizontal voice-level bars shown while receiving a command."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self._level = 0.0
        self._display = 0.0
        self._bars = [0.1] * 36
        self._active = False
        self._color = QColor("#ffb020")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            self._level = 0.0

    def set_color(self, color: str) -> None:
        self._color = QColor(color)

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))

    def _tick(self) -> None:
        self._display += (self._level - self._display) * 0.4
        for i in range(len(self._bars)):
            if self._active:
                wave = abs(math.sin(i * 0.45 + self._display * 8))
                target = 0.15 + self._display * 0.7 * wave + random.uniform(0, 0.1)
            else:
                target = 0.08
            self._bars[i] += (target - self._bars[i]) * 0.35
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._bars)
        gap = 2
        bar_w = max(2.0, (w - gap * (n - 1)) / n)
        mid = h / 2
        for i, val in enumerate(self._bars):
            bh = max(3.0, val * (h - 4))
            x = i * (bar_w + gap)
            c = QColor(self._color)
            c.setAlpha(int(70 + val * 160) if self._active else 40)
            painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(x), int(mid - bh / 2),
                int(bar_w), int(bh),
                2, 2,
            )
