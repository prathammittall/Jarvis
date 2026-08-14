"""JARVIS application entry point — tray runtime with wake word and hotkey."""

from __future__ import annotations

import sys

from app.config import get_settings
from app.core.assistant import JarvisAssistant
from app.core.events import EventType
from app.core.logger import setup_logging
from app.core.state import AssistantState


def _sync_windows_startup(settings) -> None:
    """Honor START_WITH_WINDOWS without showing a console at login."""
    try:
        from app.core import startup as win_startup
        if settings.start_with_windows and not win_startup.is_enabled():
            win_startup.enable()
        elif not settings.start_with_windows and win_startup.is_enabled():
            # Leave an existing shortcut unless the user disabled it in Settings.
            pass
    except Exception:
        pass


def run_with_ui(debug: bool = False, show_window: bool = False) -> int:
    from PySide6.QtWidgets import QApplication
    from app.core.hotkey import GlobalHotkey
    from app.ui.window import JarvisWindow
    from app.ui.tray import JarvisTray

    settings = get_settings()
    logger = setup_logging(debug=debug)
    _sync_windows_startup(settings)

    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")
    app.setQuitOnLastWindowClosed(False)

    assistant = JarvisAssistant()
    window = JarvisWindow(always_on_top=settings.ui_always_on_top)
    tray = JarvisTray(assistant, window, app)
    hotkey: GlobalHotkey | None = None

    def on_state_change(old, new):
        window.sig_state.emit(new)
        tray.sig_state.emit(new)

    assistant.set_state_callback(on_state_change)

    def on_transcription(event):
        text = event.data.get("text", "")
        window.sig_command.emit(text)

    def on_response(event):
        text = event.data.get("text", "")
        window.sig_response.emit(text)

    def on_level(event):
        window.sig_level.emit(float(event.data.get("level", 0.0)))

    def on_tool(event):
        action = event.data.get("action", "")
        window.sig_tool.emit(str(action))

    def on_tool_result(event):
        action = event.data.get("action", "")
        result = event.data.get("result", {})
        ok = result.get("success", False)
        window.sig_activity.emit(
            f"Tool · {action} · {'ok' if ok else 'failed'}"
        )

    def on_wake(event):
        window.sig_activity.emit("Wake word detected")
        window.sig_response.emit("Yes?")

    def on_speech_started(event):
        text = event.data.get("text", "")
        if text:
            window.sig_response.emit(text)
        window.sig_activity.emit("Speaking response")

    assistant.events.subscribe(EventType.TRANSCRIPTION, on_transcription)
    assistant.events.subscribe(EventType.COMMAND_RECEIVED, on_transcription)
    assistant.events.subscribe(EventType.RESPONSE, on_response)
    assistant.events.subscribe(EventType.AUDIO_LEVEL, on_level)
    assistant.events.subscribe(EventType.TOOL_SELECTED, on_tool)
    assistant.events.subscribe(EventType.TOOL_RESULT, on_tool_result)
    assistant.events.subscribe(EventType.WAKE_WORD_DETECTED, on_wake)
    assistant.events.subscribe(EventType.SPEECH_STARTED, on_speech_started)

    window.talk_requested.connect(assistant.activate)

    if settings.global_hotkey_enabled:
        hotkey = GlobalHotkey(
            spec=settings.global_hotkey or "ctrl+space",
            on_hotkey=assistant.activate,
        )
        hotkey.start()
        logger.info("Global hotkey: %s", settings.global_hotkey)

    def _shutdown():
        if hotkey:
            try:
                hotkey.stop()
            except Exception:
                pass
        try:
            assistant.stop()
        except Exception:
            pass

    app.aboutToQuit.connect(_shutdown)

    start_minimized = settings.ui_start_minimized and not show_window
    if not start_minimized:
        window.show()

    window.sig_state.emit(AssistantState.IDLE)
    assistant.preload_models()
    assistant.start()

    tray.tray.showMessage(
        "Jarvis",
        "Running in the system tray. Say Jarvis or press Ctrl+Space.",
        tray.tray.MessageIcon.Information,
        2500,
    )

    logger.info("Jarvis running in the system tray")
    return app.exec()


def run_headless(debug: bool = False) -> int:
    """No dashboard window — still uses the tray when Qt is available."""
    settings = get_settings()
    if settings.ui_enabled:
        return run_with_ui(debug=debug, show_window=False)
    logger = setup_logging(debug=debug)
    assistant = JarvisAssistant()
    assistant.preload_models()
    assistant.start()
    logger.info("JARVIS running in headless mode. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        assistant.stop()
    return 0


def run_cli(debug: bool = False) -> int:
    settings = get_settings()
    logger = setup_logging(debug=debug)

    assistant = JarvisAssistant()
    logger.info("JARVIS CLI mode. Type commands (or 'quit' to exit).")

    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() in ("quit", "exit", "q"):
            break
        result = assistant.process_text_command(text)
        print(f"JARVIS: {result.get('response', '')}")
        if debug:
            print(f"  [tool={result.get('tool')}, success={result.get('success')}]")

    return 0


def main(
    debug: bool = False,
    cli: bool = False,
    no_ui: bool = False,
    show_window: bool = False,
) -> int:
    settings = get_settings()
    settings.ensure_directories()

    if cli:
        return run_cli(debug)
    if no_ui:
        return run_headless(debug)
    return run_with_ui(debug, show_window=show_window)
