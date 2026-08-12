"""JARVIS application entry point."""

from __future__ import annotations

import sys

from app.config import get_settings
from app.core.assistant import JarvisAssistant
from app.core.events import EventType
from app.core.logger import setup_logging
from app.core.state import AssistantState


def run_with_ui(debug: bool = False) -> int:
    from PySide6.QtWidgets import QApplication
    from app.ui.window import JarvisWindow
    from app.ui.tray import JarvisTray

    settings = get_settings()
    logger = setup_logging(debug=debug)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    assistant = JarvisAssistant()
    window = JarvisWindow(always_on_top=settings.ui_always_on_top)
    tray = JarvisTray(assistant, window, app)

    def on_state_change(old, new):
        window.update_state(new)
        tray.update_status(new)

    assistant.set_state_callback(on_state_change)

    def on_status_text(event):
        window.update_command(event.data.get("text", ""))

    assistant.events.subscribe(EventType.STATUS_TEXT, on_status_text)
    assistant.events.subscribe(EventType.TRANSCRIPTION, on_status_text)

    if not settings.ui_start_minimized:
        window.show()

    window.update_state(AssistantState.IDLE)
    assistant.preload_models()
    assistant.start()

    logger.info("JARVIS UI started")
    return app.exec()


def run_headless(debug: bool = False) -> int:
    settings = get_settings()
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


def main(debug: bool = False, cli: bool = False, no_ui: bool = False) -> int:
    settings = get_settings()
    settings.ensure_directories()

    if cli:
        return run_cli(debug)
    if no_ui or not settings.ui_enabled:
        return run_headless(debug)
    return run_with_ui(debug)
