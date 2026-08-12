"""Event bus for decoupled communication."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class EventType(Enum):
    STATE_CHANGED = auto()
    WAKE_WORD_DETECTED = auto()
    COMMAND_RECEIVED = auto()
    TRANSCRIPTION = auto()
    TOOL_SELECTED = auto()
    TOOL_RESULT = auto()
    SPEECH_STARTED = auto()
    SPEECH_FINISHED = auto()
    CONFIRMATION_REQUIRED = auto()
    ERROR = auto()
    DEBUG = auto()
    STATUS_TEXT = auto()


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def emit(self, event_type: EventType, **data: Any) -> None:
        event = Event(type=event_type, data=data)
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass

    def debug(self, category: str, message: str) -> None:
        self.emit(EventType.DEBUG, category=category, message=message)
