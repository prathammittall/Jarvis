"""JARVIS status display constants."""

from app.core.state import AssistantState, STATE_LABELS

STATE_COLORS = {
    AssistantState.LISTENING_FOR_WAKE_WORD: "#00ff88",
    AssistantState.WAKE_WORD_DETECTED: "#00ccff",
    AssistantState.LISTENING_FOR_COMMAND: "#ffaa00",
    AssistantState.TRANSCRIBING: "#ff8800",
    AssistantState.THINKING: "#aa88ff",
    AssistantState.EXECUTING: "#ff4488",
    AssistantState.SPEAKING: "#4488ff",
    AssistantState.AWAITING_CONFIRMATION: "#ff6644",
    AssistantState.ERROR: "#ff0044",
    AssistantState.STOPPED: "#666666",
    AssistantState.IDLE: "#444444",
}

STATE_ICONS = {
    AssistantState.LISTENING_FOR_WAKE_WORD: "◉",
    AssistantState.WAKE_WORD_DETECTED: "◈",
    AssistantState.LISTENING_FOR_COMMAND: "◎",
    AssistantState.TRANSCRIBING: "◐",
    AssistantState.THINKING: "◑",
    AssistantState.EXECUTING: "◒",
    AssistantState.SPEAKING: "◓",
    AssistantState.AWAITING_CONFIRMATION: "◔",
    AssistantState.ERROR: "✕",
    AssistantState.STOPPED: "○",
    AssistantState.IDLE: "·",
}
