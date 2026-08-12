"""Core JARVIS assistant orchestrator."""

from __future__ import annotations

import sys
import threading
import time
from typing import Callable

if sys.platform == "win32":
    import winsound

from app.brain.agent import Agent
from app.config import get_settings
from app.core.events import EventBus, EventType
from app.core.logger import get_logger
from app.core.state import AssistantState, StateMachine
from app.speech.stt import SpeechToText
from app.speech.tts import TextToSpeech
from app.wakeword.audio import AudioCapture
from app.wakeword.detector import create_detector

logger = get_logger("assistant")


class JarvisAssistant:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._settings = get_settings()
        self._events = event_bus or EventBus()
        self._state = StateMachine()
        self._agent = Agent(self._events)
        self._stt = SpeechToText()
        self._tts = TextToSpeech()
        self._capture = AudioCapture()
        self._wake_detector = None
        self._running = False
        self._processing = False
        self._last_command = ""
        self._on_state_change: Callable | None = None

        self._state.add_listener(self._on_state_changed)

    @property
    def state(self) -> StateMachine:
        return self._state

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def events(self) -> EventBus:
        return self._events

    @property
    def last_command(self) -> str:
        return self._last_command

    def set_state_callback(self, callback: Callable) -> None:
        self._on_state_change = callback

    def _on_state_changed(self, old, new) -> None:
        logger.info("State: %s -> %s", old.name, new.name)
        self._events.emit(EventType.STATE_CHANGED, old=old, new=new, label=self._state.label)
        if self._on_state_change:
            self._on_state_change(old, new)

    def _debug(self, category: str, message: str) -> None:
        if self._settings.debug_mode:
            self._events.debug(category, message)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("JARVIS starting...")

        if self._settings.wake_word_enabled:
            self._wake_detector = create_detector(on_detected=self._on_wake_word)
            self._wake_detector.start()
            self._state.transition(AssistantState.LISTENING_FOR_WAKE_WORD)
        else:
            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)

        logger.info("JARVIS ready.")

    def stop(self) -> None:
        self._running = False
        if self._wake_detector:
            self._wake_detector.stop()
        self._tts.stop()
        self._state.transition(AssistantState.STOPPED)
        logger.info("JARVIS stopped.")

    def toggle_wake_word(self, enabled: bool) -> None:
        if self._wake_detector:
            self._wake_detector.enabled = enabled

    def _on_wake_word(self) -> None:
        if self._processing or not self._running:
            return
        self._processing = True
        threading.Thread(target=self._handle_wake_word, daemon=True).start()

    def _handle_wake_word(self) -> None:
        try:
            self._debug("WAKEWORD", "Detected: Jarvis")
            self._events.emit(EventType.WAKE_WORD_DETECTED)
            self._state.transition(AssistantState.WAKE_WORD_DETECTED)

            if self._settings.activation_sound and sys.platform == "win32":
                try:
                    winsound.Beep(800, 150)
                except Exception:
                    pass

            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
            self._tts.speak("Yes?", block=True)

            self._listen_and_process()
        except Exception as e:
            logger.error("Wake word handling error: %s", e)
            self._state.transition(AssistantState.ERROR)
        finally:
            self._processing = False
            if self._running:
                self._state.transition(AssistantState.LISTENING_FOR_WAKE_WORD)

    def _listen_and_process(self) -> None:
        self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
        audio = self._capture.record_until_silence()

        if len(audio) == 0:
            self._tts.speak("I didn't hear anything.")
            return

        self._state.transition(AssistantState.TRANSCRIBING)
        text = self._stt.transcribe(audio)
        self._last_command = text
        self._events.emit(EventType.TRANSCRIPTION, text=text)
        self._events.emit(EventType.COMMAND_RECEIVED, text=text)
        self._events.emit(EventType.STATUS_TEXT, text=text)

        if not text:
            self._tts.speak("I didn't catch that.")
            return

        self._process_text(text)

    def _process_text(self, text: str) -> None:
        self._state.transition(AssistantState.THINKING)
        result = self._agent.process_command(text)

        if result.get("awaiting_confirmation"):
            self._state.transition(AssistantState.AWAITING_CONFIRMATION)
            self._state.transition(AssistantState.SPEAKING)
            self._events.emit(EventType.SPEECH_STARTED)
            self._tts.speak(result["response"])
            self._events.emit(EventType.SPEECH_FINISHED)

            # Listen for confirmation
            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
            audio = self._capture.record_until_silence(max_duration=5.0)
            if len(audio) > 0:
                confirm_text = self._stt.transcribe(audio)
                self._state.transition(AssistantState.THINKING)
                result = self._agent.process_command(confirm_text)
        elif result.get("tool"):
            self._state.transition(AssistantState.EXECUTING)

        response = result.get("response", "")
        if response:
            self._state.transition(AssistantState.SPEAKING)
            self._events.emit(EventType.SPEECH_STARTED)
            self._tts.speak(response)
            self._events.emit(EventType.SPEECH_FINISHED)

    def process_text_command(self, text: str) -> dict:
        """Process a text command directly (for CLI/debug mode)."""
        self._last_command = text
        self._state.transition(AssistantState.THINKING)
        result = self._agent.process_command(text)
        response = result.get("response", "")
        if response and self._settings.tts_enabled:
            self._state.transition(AssistantState.SPEAKING)
            self._tts.speak(response)
        return result

    def preload_models(self) -> None:
        """Preload STT and TTS models in background."""
        threading.Thread(target=self._stt.preload, daemon=True).start()
        threading.Thread(target=self._tts.preload, daemon=True).start()
