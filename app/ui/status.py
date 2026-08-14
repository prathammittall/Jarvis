"""UI status labels, colors, and human-readable phase messages."""

from __future__ import annotations

from app.core.state import AssistantState, STATE_LABELS

__all__ = [
    "STATE_COLORS",
    "STATE_MESSAGES",
    "STATE_HINTS",
    "STATE_LABELS",
    "VOICE_INPUT_STATES",
    "IDLE_PULSE_STATES",
]

STATE_COLORS = {
    AssistantState.IDLE: "#5a6a7a",
    AssistantState.LISTENING_FOR_WAKE_WORD: "#2ee6a6",
    AssistantState.WAKE_WORD_DETECTED: "#3ecfff",
    AssistantState.LISTENING_FOR_COMMAND: "#ffb020",
    AssistantState.TRANSCRIBING: "#ff8c3a",
    AssistantState.THINKING: "#7eb8ff",
    AssistantState.EXECUTING: "#ff6b9d",
    AssistantState.SPEAKING: "#4da3ff",
    AssistantState.AWAITING_CONFIRMATION: "#ff7a45",
    AssistantState.ERROR: "#ff4d6d",
    AssistantState.STOPPED: "#6b7785",
}

STATE_MESSAGES = {
    AssistantState.IDLE: "Standing by",
    AssistantState.LISTENING_FOR_WAKE_WORD: "Say \"Jarvis\" to activate",
    AssistantState.WAKE_WORD_DETECTED: "Activated — ready for your command",
    AssistantState.LISTENING_FOR_COMMAND: "Receiving voice command…",
    AssistantState.TRANSCRIBING: "Converting speech to text…",
    AssistantState.THINKING: "Understanding your request…",
    AssistantState.EXECUTING: "Running action…",
    AssistantState.SPEAKING: "Speaking response…",
    AssistantState.AWAITING_CONFIRMATION: "Waiting for your confirmation…",
    AssistantState.ERROR: "Something went wrong",
    AssistantState.STOPPED: "Offline",
}

STATE_HINTS = {
    AssistantState.IDLE: "Systems initializing",
    AssistantState.LISTENING_FOR_WAKE_WORD: "Wake word listening — or click Talk",
    AssistantState.WAKE_WORD_DETECTED: "Microphone engaged",
    AssistantState.LISTENING_FOR_COMMAND: "Speak clearly — stop when finished",
    AssistantState.TRANSCRIBING: "Local speech recognition",
    AssistantState.THINKING: "Consulting Gemini",
    AssistantState.EXECUTING: "Tool in progress",
    AssistantState.SPEAKING: "Local voice synthesis",
    AssistantState.AWAITING_CONFIRMATION: "Say yes to continue, or no to cancel",
    AssistantState.ERROR: "Check logs for details",
    AssistantState.STOPPED: "Assistant stopped",
}

# Active voice-input states (show waveform / live mic feedback)
VOICE_INPUT_STATES = {
    AssistantState.LISTENING_FOR_COMMAND,
    AssistantState.WAKE_WORD_DETECTED,
}

# Soft idle pulse states
IDLE_PULSE_STATES = {
    AssistantState.LISTENING_FOR_WAKE_WORD,
    AssistantState.IDLE,
}
