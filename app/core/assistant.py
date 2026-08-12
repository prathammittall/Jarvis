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

    def activate(self) -> None:
        """Manual activation (click-to-talk / push-to-talk)."""
        self._on_wake_word()

    def _pause_wake(self) -> None:
        if self._wake_detector and hasattr(self._wake_detector, "pause"):
            self._wake_detector.pause()

    def _resume_wake(self) -> None:
        if self._wake_detector and hasattr(self._wake_detector, "resume"):
            self._wake_detector.resume()

    def _on_wake_word(self) -> None:
        if self._processing or not self._running:
            return
        self._processing = True
        self._pause_wake()
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

            # Brief pause so wake audio / beep doesn't get captured as the command
            time.sleep(0.35)
            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
            self._tts.speak("Yes?", block=True)
            time.sleep(0.25)

            self._listen_and_process()
        except Exception as e:
            logger.error("Wake word handling error: %s", e, exc_info=True)
            self._state.force(AssistantState.ERROR)
            self._events.emit(EventType.RESPONSE, text=f"Error: {e}")
            time.sleep(1.0)
        finally:
            self._processing = False
            if self._running:
                self._state.force(AssistantState.LISTENING_FOR_WAKE_WORD)
                self._resume_wake()
                logger.info("Returned to wake-word listening")

    def _emit_level(self, level: float) -> None:
        self._events.emit(EventType.AUDIO_LEVEL, level=level)

    def _listen_and_process(self) -> None:
        self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
        self._events.emit(EventType.STATUS_TEXT, text="Receiving voice command…")
        audio = self._capture.record_until_silence(on_level=self._emit_level)

        if len(audio) == 0:
            msg = "I didn't hear anything."
            self._events.emit(EventType.RESPONSE, text=msg)
            self._tts.speak(msg)
            return

        self._state.transition(AssistantState.TRANSCRIBING)
        self._events.emit(EventType.STATUS_TEXT, text="Converting speech to text…")
        text = self._stt.transcribe(audio)
        self._last_command = text
        self._events.emit(EventType.TRANSCRIPTION, text=text)
        self._events.emit(EventType.COMMAND_RECEIVED, text=text)
        self._events.emit(EventType.STATUS_TEXT, text=text)

        if not text:
            from app.brain.responses import error_response
            msg = error_response("not_caught")
            self._events.emit(EventType.RESPONSE, text=msg)
            self._tts.speak(msg)
            return

        self._debug("STT", f'"{text}" (whisper_lang={getattr(self._stt, "last_language", "?")})')
        self._process_text(text)

    def _process_text(self, text: str) -> None:
        # Fast path skips "Thinking" UI state
        from app.brain.fast_commands import get_fast_router
        if self._settings.fast_commands_enabled and get_fast_router().match(text):
            self._state.transition(AssistantState.EXECUTING)
        else:
            self._state.transition(AssistantState.THINKING)

        result = self._agent.process_command(text)

        if result.get("source") == "fast" and not result.get("awaiting_confirmation"):
            if self._state.state != AssistantState.EXECUTING:
                self._state.transition(AssistantState.EXECUTING)

        if result.get("awaiting_confirmation"):
            self._state.transition(AssistantState.AWAITING_CONFIRMATION)
            self._state.transition(AssistantState.SPEAKING)
            response = result.get("response", "")
            self._events.emit(EventType.RESPONSE, text=response)
            self._events.emit(EventType.SPEECH_STARTED, text=response)
            tts_start = time.perf_counter()
            self._tts.speak(response, language=result.get("language"))
            logger.info("Perf: TTS=%.2fs", time.perf_counter() - tts_start)
            self._events.emit(EventType.SPEECH_FINISHED)

            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
            self._events.emit(EventType.STATUS_TEXT, text="Waiting for confirmation…")
            audio = self._capture.record_until_silence(
                max_duration=5.0, on_level=self._emit_level,
            )
            if len(audio) > 0:
                confirm_text = self._stt.transcribe(audio)
                self._events.emit(EventType.TRANSCRIPTION, text=confirm_text)
                self._state.transition(AssistantState.THINKING)
                result = self._agent.process_command(confirm_text)
        elif result.get("tool") and result.get("source") != "fast":
            self._state.transition(AssistantState.EXECUTING)

        response = result.get("response", "")
        if response:
            self._state.transition(AssistantState.SPEAKING)
            self._events.emit(EventType.RESPONSE, text=response)
            self._events.emit(EventType.SPEECH_STARTED, text=response)
            tts_start = time.perf_counter()
            self._tts.speak(response, language=result.get("language"))
            logger.info("Perf: TTS=%.2fs", time.perf_counter() - tts_start)
            self._events.emit(EventType.SPEECH_FINISHED)

    def process_text_command(self, text: str) -> dict:
        """Process a text command directly (for CLI/debug mode)."""
        self._last_command = text
        if self._settings.fast_commands_enabled:
            from app.brain.fast_commands import get_fast_router
            if get_fast_router().match(text):
                self._state.transition(AssistantState.EXECUTING)
            else:
                self._state.transition(AssistantState.THINKING)
        else:
            self._state.transition(AssistantState.THINKING)

        result = self._agent.process_command(text)
        response = result.get("response", "")
        if response and self._settings.tts_enabled:
            self._state.transition(AssistantState.SPEAKING)
            self._tts.speak(response, language=result.get("language"))
        return result

    def preload_models(self) -> None:
        """Preload STT/TTS and warm LLM providers in background (non-blocking)."""
        threading.Thread(target=self._stt.preload, daemon=True, name="preload-stt").start()
        threading.Thread(target=self._tts.preload, daemon=True, name="preload-tts").start()
        threading.Thread(target=self._warmup_providers, daemon=True, name="llm-warmup").start()

    def _warmup_providers(self) -> None:
        try:
            self._agent.providers.warmup_all()
        except Exception as e:
            logger.warning("Provider warmup thread error: %s", e)
