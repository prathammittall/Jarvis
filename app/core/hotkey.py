"""Global hotkey listener for Windows (RegisterHotKey).

The registration and message pump live on one dedicated thread so
Ctrl+Space (or a configured combo) can wake Jarvis from any app.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

from app.core.logger import get_logger

logger = get_logger("hotkey")

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_SPACE = 0x20
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_TAB = 0x09

_VK_SPECIAL = {
    "space": VK_SPACE,
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "esc": VK_ESCAPE,
    "escape": VK_ESCAPE,
    "tab": VK_TAB,
}


def parse_hotkey(spec: str) -> tuple[int, int]:
    """Parse 'ctrl+space' / 'ctrl+shift+j' into (modifiers, virtual_key)."""
    raw = (spec or "ctrl+space").strip().lower()
    parts = [p.strip() for p in raw.replace("-", "+").split("+") if p.strip()]
    if not parts:
        raise ValueError("Empty hotkey")

    mods = 0
    key: str | None = None
    for part in parts:
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part in ("alt", "menu"):
            mods |= MOD_ALT
        elif part in ("shift",):
            mods |= MOD_SHIFT
        elif part in ("win", "windows", "meta", "super"):
            mods |= MOD_WIN
        else:
            key = part

    if not key:
        raise ValueError(f"No key in hotkey spec: {spec!r}")

    if key in _VK_SPECIAL:
        vk = _VK_SPECIAL[key]
    elif len(key) == 1 and ("a" <= key <= "z" or "0" <= key <= "9"):
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            vk = 0x70 + n - 1
        else:
            raise ValueError(f"Unsupported function key: {key}")
    else:
        raise ValueError(f"Unsupported hotkey key: {key}")

    return mods, vk


class GlobalHotkey:
    """Windows-wide hotkey. Invokes on_hotkey on the listener thread."""

    def __init__(
        self,
        spec: str = "ctrl+space",
        on_hotkey: Callable[[], None] | None = None,
        hotkey_id: int = 1,
    ) -> None:
        self._spec = spec
        self._on_hotkey = on_hotkey
        self._hotkey_id = hotkey_id
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._thread_id: int | None = None

    @property
    def spec(self) -> str:
        return self._spec

    def start(self) -> None:
        if self._running.is_set():
            return
        try:
            parse_hotkey(self._spec)
        except ValueError as e:
            logger.error("Invalid hotkey %r: %s", self._spec, e)
            return
        self._running.set()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="hotkey")
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread_id:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("Global hotkey stopped")

    def _loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        try:
            mods, vk = parse_hotkey(self._spec)
        except ValueError as e:
            logger.error("Hotkey parse failed: %s", e)
            self._running.clear()
            return

        user32 = ctypes.windll.user32
        try:
            self._thread_id = threading.get_ident()
        except Exception:
            self._thread_id = None

        # RegisterHotKey must be called on this thread (same as the message pump).
        if not user32.RegisterHotKey(None, self._hotkey_id, mods | MOD_NOREPEAT, vk):
            err = ctypes.GetLastError()
            logger.error(
                "Failed to register hotkey %s (error %s). It may already be in use.",
                self._spec,
                err,
            )
            self._running.clear()
            return

        logger.info("Global hotkey registered: %s", self._spec)
        msg = wintypes.MSG()
        try:
            while self._running.is_set():
                # Timeout pump so stop() can exit even without WM_QUIT
                got = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
                if got:
                    if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                        logger.info("Hotkey pressed: %s", self._spec)
                        if self._on_hotkey:
                            try:
                                self._on_hotkey()
                            except Exception as e:
                                logger.error("Hotkey callback error: %s", e)
                    elif msg.message == WM_QUIT:
                        break
                    else:
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.03)
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)
