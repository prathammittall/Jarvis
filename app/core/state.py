"""Assistant state machine."""

from __future__ import annotations

from enum import Enum, auto


class AssistantState(Enum):
    IDLE = auto()
    LISTENING_FOR_WAKE_WORD = auto()
    WAKE_WORD_DETECTED = auto()
    LISTENING_FOR_COMMAND = auto()
    TRANSCRIBING = auto()
    THINKING = auto()
    EXECUTING = auto()
    SPEAKING = auto()
    AWAITING_CONFIRMATION = auto()
    ERROR = auto()
    STOPPED = auto()


STATE_LABELS = {
    AssistantState.IDLE: "Idle",
    AssistantState.LISTENING_FOR_WAKE_WORD: "Listening",
    AssistantState.WAKE_WORD_DETECTED: "Activated",
    AssistantState.LISTENING_FOR_COMMAND: "Listening for command",
    AssistantState.TRANSCRIBING: "Transcribing",
    AssistantState.THINKING: "Thinking",
    AssistantState.EXECUTING: "Executing",
    AssistantState.SPEAKING: "Speaking",
    AssistantState.AWAITING_CONFIRMATION: "Awaiting confirmation",
    AssistantState.ERROR: "Error",
    AssistantState.STOPPED: "Stopped",
}

# Valid state transitions
VALID_TRANSITIONS: dict[AssistantState, set[AssistantState]] = {
    AssistantState.IDLE: {AssistantState.LISTENING_FOR_WAKE_WORD, AssistantState.STOPPED},
    AssistantState.LISTENING_FOR_WAKE_WORD: {
        AssistantState.WAKE_WORD_DETECTED,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.WAKE_WORD_DETECTED: {
        AssistantState.LISTENING_FOR_COMMAND,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.LISTENING_FOR_COMMAND: {
        AssistantState.TRANSCRIBING,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.TRANSCRIBING: {
        AssistantState.THINKING,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.THINKING: {
        AssistantState.EXECUTING,
        AssistantState.SPEAKING,
        AssistantState.AWAITING_CONFIRMATION,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.EXECUTING: {
        AssistantState.SPEAKING,
        AssistantState.AWAITING_CONFIRMATION,
        AssistantState.THINKING,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.SPEAKING: {
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.LISTENING_FOR_COMMAND,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.AWAITING_CONFIRMATION: {
        AssistantState.EXECUTING,
        AssistantState.SPEAKING,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.ERROR,
        AssistantState.STOPPED,
    },
    AssistantState.ERROR: {
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.STOPPED,
    },
    AssistantState.STOPPED: {AssistantState.IDLE, AssistantState.LISTENING_FOR_WAKE_WORD},
}


class StateMachine:
    def __init__(self) -> None:
        self._state = AssistantState.IDLE
        self._listeners: list = []

    @property
    def state(self) -> AssistantState:
        return self._state

    @property
    def label(self) -> str:
        return STATE_LABELS.get(self._state, "Unknown")

    def add_listener(self, callback) -> None:
        self._listeners.append(callback)

    def transition(self, new_state: AssistantState) -> bool:
        allowed = VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed and new_state != self._state:
            return False
        old = self._state
        self._state = new_state
        for cb in self._listeners:
            try:
                cb(old, new_state)
            except Exception:
                pass
        return True

    def force(self, new_state: AssistantState) -> None:
        old = self._state
        self._state = new_state
        for cb in self._listeners:
            try:
                cb(old, new_state)
            except Exception:
                pass
