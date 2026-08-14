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
        self._listening_enabled = bool(self._settings.listening_enabled)
        self._last_command = ""
        self._on_state_change: Callable | None = None
        self._turn_t0 = 0.0
        self._wake_ms = 0.0

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
        logger.info("Jarvis started")

        if self._settings.wake_word_enabled and self._listening_enabled:
            self._wake_detector = create_detector(on_detected=self._on_wake_word)
            self._wake_detector.start()
            self._state.transition(AssistantState.LISTENING_FOR_WAKE_WORD)
            logger.info("Wake-word listener started")
        elif not self._listening_enabled:
            self._state.transition(AssistantState.IDLE)
            logger.info("Listening is paused — use the tray or hotkey to activate")
        else:
            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)

        logger.info("Jarvis ready.")

    def stop(self) -> None:
        self._running = False
        if self._wake_detector:
            self._wake_detector.stop()
        try:
            self._tts.stop()
        except Exception:
            pass
        self._state.force(AssistantState.STOPPED)
        logger.info("Jarvis stopped.")

    def restart(self) -> None:
        logger.info("Restarting Jarvis")
        self.stop()
        time.sleep(0.3)
        self.start()

    def toggle_wake_word(self, enabled: bool) -> None:
        self.set_listening_enabled(enabled)

    def set_listening_enabled(self, enabled: bool) -> None:
        self._listening_enabled = enabled
        if self._wake_detector:
            self._wake_detector.enabled = enabled
        if enabled:
            if self._running and self._settings.wake_word_enabled:
                if self._wake_detector is None:
                    self._wake_detector = create_detector(on_detected=self._on_wake_word)
                    self._wake_detector.start()
                self._resume_wake()
                self._state.force(AssistantState.LISTENING_FOR_WAKE_WORD)
            logger.info("Listening enabled")
        else:
            self._pause_wake()
            if self._running:
                self._state.force(AssistantState.IDLE)
            logger.info("Listening paused")

    def is_listening(self) -> bool:
        return bool(self._running and self._listening_enabled)

    def activate(self) -> None:
        """Manual activation (hotkey / click-to-talk / push-to-talk)."""
        logger.info("Listening activated (hotkey or tray)")
        self._on_wake_word()

    def _pause_wake(self) -> None:
        if self._wake_detector and hasattr(self._wake_detector, "pause"):
            self._wake_detector.pause()

    def _resume_wake(self) -> None:
        if not self._listening_enabled:
            return
        if self._wake_detector and hasattr(self._wake_detector, "resume"):
            self._wake_detector.resume()

    def _wait_tts_idle(self, timeout: float = 8.0) -> None:
        """Do not resume the mic until Jarvis has finished speaking."""
        deadline = time.time() + timeout
        try:
            while self._tts.is_speaking and time.time() < deadline:
                time.sleep(0.05)
        except Exception:
            pass
        time.sleep(0.15)

    def _on_wake_word(self) -> None:
        if self._processing or not self._running:
            return
        try:
            if self._tts.is_speaking:
                return
        except Exception:
            pass
        self._processing = True
        self._pause_wake()
        threading.Thread(target=self._handle_wake_word, daemon=True, name="command-turn").start()

    def _handle_wake_word(self) -> None:
        self._turn_t0 = time.perf_counter()
        self._wake_ms = 0.0
        try:
            logger.info("Wake word detected")
            self._debug("WAKEWORD", "Detected: Jarvis")
            self._events.emit(EventType.WAKE_WORD_DETECTED)
            self._state.transition(AssistantState.AWAKE)

            if self._settings.activation_sound and sys.platform == "win32":
                try:
                    winsound.Beep(800, 150)
                except Exception:
                    pass

            # Speak the ack and wait so we do not transcribe our own voice
            try:
                self._tts.speak("Yes?", block=True)
            except Exception as e:
                logger.warning("Acknowledgement TTS failed: %s", e)

            self._wake_ms = (time.perf_counter() - self._turn_t0) * 1000.0
            logger.info("Listening for command")
            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
            self._listen_and_process()
        except Exception as e:
            logger.error("Wake word handling error: %s", e, exc_info=True)
            self._state.force(AssistantState.ERROR)
            try:
                self._tts.speak("Sorry, something went wrong.")
            except Exception:
                pass
            self._events.emit(EventType.RESPONSE, text="Sorry, something went wrong.")
            time.sleep(0.5)
        finally:
            self._wait_tts_idle()
            self._processing = False
            if self._running:
                if self._listening_enabled and self._settings.wake_word_enabled:
                    self._state.force(AssistantState.LISTENING_FOR_WAKE_WORD)
                    self._resume_wake()
                    logger.info("Returned to wake-word listening")
                else:
                    self._state.force(AssistantState.IDLE)

    def _emit_level(self, level: float) -> None:
        self._events.emit(EventType.AUDIO_LEVEL, level=level)

    def _listen_and_process(self) -> None:
        self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
        self._events.emit(EventType.STATUS_TEXT, text="Receiving voice command…")
        try:
            audio = self._capture.record_until_silence(on_level=self._emit_level)
        except Exception as e:
            logger.error("Microphone unavailable: %s", e)
            msg = "I couldn't access the microphone."
            self._events.emit(EventType.RESPONSE, text=msg)
            try:
                self._tts.speak(msg)
            except Exception:
                pass
            return

        if len(audio) == 0:
            msg = "I didn't hear anything."
            self._events.emit(EventType.RESPONSE, text=msg)
            try:
                self._tts.speak(msg)
            except Exception:
                pass
            return

        self._state.transition(AssistantState.TRANSCRIBING)
        self._events.emit(EventType.STATUS_TEXT, text="Converting speech to text…")
        stt_start = time.perf_counter()
        try:
            text = self._stt.transcribe(audio)
        except Exception as e:
            logger.error("Speech-to-text failed: %s", e)
            msg = "I couldn't understand that."
            self._events.emit(EventType.RESPONSE, text=msg)
            try:
                self._tts.speak(msg)
            except Exception:
                pass
            return
        stt_s = time.perf_counter() - stt_start
        self._last_command = text
        self._events.emit(EventType.TRANSCRIPTION, text=text)
        self._events.emit(EventType.COMMAND_RECEIVED, text=text)
        self._events.emit(EventType.STATUS_TEXT, text=text)

        if not text:
            from app.brain.responses import error_response
            msg = error_response("not_caught")
            self._events.emit(EventType.RESPONSE, text=msg)
            try:
                self._tts.speak(msg)
            except Exception:
                pass
            return

        logger.info("Command: %s", text)
        self._debug("STT", f'"{text}" (whisper_lang={getattr(self._stt, "last_language", "?")})')
        self._process_text(text, stt_s=stt_s)

    def _process_text(self, text: str, stt_s: float = 0.0) -> None:
        # Fast path skips "Thinking" UI state
        from app.brain.fast_commands import get_fast_router
        if self._settings.fast_commands_enabled and get_fast_router().match(text):
            logger.info("Local command detected")
            self._state.transition(AssistantState.EXECUTING)
        else:
            self._state.transition(AssistantState.PROCESSING)

        try:
            result = self._agent.process_command(text)
        except Exception as e:
            logger.error("Command processing failed: %s", e, exc_info=True)
            result = {
                "response": "Sorry, I'm unable to process that right now.",
                "success": False,
                "source": "none",
                "timings": {},
            }

        timings = result.setdefault("timings", {})
        timings["stt"] = stt_s or timings.get("stt", getattr(self._stt, "last_latency", 0.0))
        timings["wake"] = self._wake_ms / 1000.0

        if result.get("source") == "fast":
            logger.info("Opening / executing local action")
        elif result.get("source") == "gemini":
            logger.info("Gemini response")
        elif result.get("source") == "ollama":
            logger.info("Ollama fallback")

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
            try:
                self._tts.speak(response, language=result.get("language"))
            except Exception as e:
                logger.warning("TTS failed: %s", e)
            timings["tts"] = time.perf_counter() - tts_start
            self._events.emit(EventType.SPEECH_FINISHED)

            self._state.transition(AssistantState.LISTENING_FOR_COMMAND)
            self._events.emit(EventType.STATUS_TEXT, text="Waiting for confirmation…")
            try:
                audio = self._capture.record_until_silence(
                    max_duration=5.0, on_level=self._emit_level,
                )
            except Exception as e:
                logger.error("Microphone unavailable during confirmation: %s", e)
                audio = []
            if len(audio) > 0:
                confirm_text = self._stt.transcribe(audio)
                self._events.emit(EventType.TRANSCRIPTION, text=confirm_text)
                self._state.transition(AssistantState.PROCESSING)
                result = self._agent.process_command(confirm_text)
                timings = result.setdefault("timings", {})
        elif result.get("tool") and result.get("source") != "fast":
            self._state.transition(AssistantState.EXECUTING)

        response = result.get("response", "")
        if response:
            self._state.transition(AssistantState.SPEAKING)
            self._events.emit(EventType.RESPONSE, text=response)
            self._events.emit(EventType.SPEECH_STARTED, text=response)
            tts_start = time.perf_counter()
            # Wait for TTS so we never resume wake-word on our own voice
            try:
                self._tts.speak(response, language=result.get("language"), block=True)
            except Exception as e:
                logger.warning("TTS failed: %s", e)
            timings["tts"] = time.perf_counter() - tts_start
            logger.info("Action completed")
            self._events.emit(EventType.SPEECH_FINISHED)

        if self._turn_t0:
            timings["total"] = time.perf_counter() - self._turn_t0
        self._agent._log_perf(timings, label=str(result.get("source") or "turn").upper())

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
