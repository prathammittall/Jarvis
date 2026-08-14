"""WhatsApp Web in Google Chrome — open chats and send messages.

Uses the installed Chrome profile (so an existing WhatsApp Web login is reused).
Does not send microphone audio or chat contents to Gemini.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any
from urllib.parse import quote

from app.config import PROJECT_ROOT, get_settings
from app.core.logger import get_logger
from app.tools.registry import RiskLevel, ToolDefinition

logger = get_logger("whatsapp")

WHATSAPP_WEB = "https://web.whatsapp.com"
WHATSAPP_SEND = "https://web.whatsapp.com/send"


def _contacts_path():
    settings = get_settings()
    rel = getattr(settings, "contacts_config", "config/contacts.json")
    return PROJECT_ROOT / rel


def load_contacts() -> dict[str, str]:
    path = _contacts_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {
            str(k).strip().lower(): str(v).strip()
            for k, v in data.items()
            if not str(k).startswith("_") and str(v).strip()
        }
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not load contacts.json: %s", e)
        return {}


def lookup_phone(name: str) -> str | None:
    if not name:
        return None
    contacts = load_contacts()
    key = re.sub(r"\s+", " ", name.strip().lower())
    if key in contacts:
        return contacts[key]
    for alias, phone in contacts.items():
        if alias in key or key in alias:
            return phone
    return None


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    settings = get_settings()
    cc = re.sub(r"\D", "", getattr(settings, "whatsapp_country_code", "") or "")
    if cc and len(digits) == 10:
        digits = cc + digits
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def _chrome_path() -> str | None:
    from app.tools.applications import _find_executable
    path = _find_executable("chrome")
    if path and os.path.isfile(path):
        return path
    return None


def open_in_chrome(url: str) -> bool:
    """Open a URL in Google Chrome (reuses a running Chrome instance when possible)."""
    chrome = _chrome_path()
    try:
        if chrome:
            subprocess.Popen([chrome, url], shell=False)
            logger.info("Opened in Chrome: %s", url.split("?")[0])
            return True
        subprocess.Popen(f'start chrome "{url}"', shell=True)
        logger.info("Opened via start chrome: %s", url.split("?")[0])
        return True
    except Exception as e:
        logger.error("Failed to open Chrome: %s", e)
        try:
            import webbrowser
            webbrowser.open(url)
            return True
        except Exception:
            return False


def _focus_whatsapp_chrome(timeout: float = 12.0) -> bool:
    """Bring the Chrome/WhatsApp window to the foreground."""
    try:
        import win32con
        import win32gui
    except ImportError:
        return False

    deadline = time.time() + timeout
    hwnd_found = 0

    def _scan() -> int:
        found = 0

        def cb(hwnd, _):
            nonlocal found
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            low = title.lower()
            if "whatsapp" in low:
                found = hwnd
                return False
            return True

        win32gui.EnumWindows(cb, None)
        if found:
            return found

        def cb_chrome(hwnd, _):
            nonlocal found
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            if "chrome" in title.lower() and title.strip():
                found = hwnd
                return False
            return True

        win32gui.EnumWindows(cb_chrome, None)
        return found

    while time.time() < deadline:
        hwnd_found = _scan()
        if hwnd_found:
            break
        time.sleep(0.35)

    if not hwnd_found:
        return False
    try:
        win32gui.ShowWindow(hwnd_found, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd_found)
        time.sleep(0.25)
        return True
    except Exception as e:
        logger.debug("Could not focus Chrome: %s", e)
        return False


def _paste(text: str) -> bool:
    """Paste Unicode text (works for Hindi names/messages). Restores clipboard."""
    try:
        import win32clipboard
        import win32com.client
        import win32con
    except ImportError:
        return False

    previous = None
    try:
        win32clipboard.OpenClipboard()
        try:
            previous = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        except Exception:
            previous = None
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("^v")
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.warning("Paste failed: %s", e)
        return False
    finally:
        if previous is not None:
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(previous, win32con.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception:
                pass


def _send_keys(keys: str) -> bool:
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys(keys)
        return True
    except Exception as e:
        logger.debug("SendKeys failed: %s", e)
        return False


def _open_whatsapp(args: dict[str, Any]) -> dict[str, Any]:
    if not open_in_chrome(WHATSAPP_WEB):
        return {"success": False, "error": "Could not open Chrome for WhatsApp Web."}
    return {"success": True, "message": "Opening WhatsApp Web."}


def _send_whatsapp(args: dict[str, Any]) -> dict[str, Any]:
    contact = (args.get("contact") or args.get("name") or "").strip()
    message = (args.get("message") or args.get("text") or "").strip()
    phone = (args.get("phone") or "").strip()

    if not contact and not phone:
        opened = _open_whatsapp({})
        if opened.get("success"):
            opened["message"] = "Opening WhatsApp Web. Who should I message?"
        return opened

    if not phone:
        phone = lookup_phone(contact) or ""
    phone_digits = normalize_phone(phone) if phone else ""

    display = contact or phone_digits or "the chat"

    if phone_digits:
        url = f"{WHATSAPP_SEND}?phone={phone_digits}"
        if message:
            url += f"&text={quote(message)}"
        if not open_in_chrome(url):
            return {"success": False, "error": "Could not open WhatsApp Web in Chrome."}
        _focus_whatsapp_chrome(timeout=14.0)
        time.sleep(2.5)
        if message:
            _send_keys("{ENTER}")
            time.sleep(0.4)
            _send_keys("{ENTER}")
            return {
                "success": True,
                "message": f"Sending that to {display} on WhatsApp.",
            }
        return {
            "success": True,
            "message": f"Opening WhatsApp with {display}.",
        }

    # No saved number — open WhatsApp Web and search the chat by name
    if not open_in_chrome(WHATSAPP_WEB):
        return {"success": False, "error": "Could not open WhatsApp Web in Chrome."}

    focused = _focus_whatsapp_chrome(timeout=14.0)
    if not focused:
        return {
            "success": True,
            "message": (
                f"WhatsApp Web is open. Search for {display} "
                "and send the message if it is not already logged in."
            ),
        }

    time.sleep(1.0)
    # WhatsApp Web search shortcut
    _send_keys("^%{/}")
    time.sleep(0.45)
    if not _paste(contact):
        _send_keys(contact)
    time.sleep(0.35)
    _send_keys("{ENTER}")
    time.sleep(0.8)

    if not message:
        return {"success": True, "message": f"Opening WhatsApp with {display}."}

    if not _paste(message):
        _send_keys(message)
    time.sleep(0.25)
    _send_keys("{ENTER}")
    logger.info("WhatsApp message sent via search to %s", display)
    return {"success": True, "message": f"Sending that to {display} on WhatsApp."}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="open_whatsapp",
        description="Open WhatsApp Web in Google Chrome",
        parameters={},
        required=[],
        risk_level=RiskLevel.SAFE,
        execute=_open_whatsapp,
    ))
    registry.register(ToolDefinition(
        name="send_whatsapp_message",
        description=(
            "Send a WhatsApp message via WhatsApp Web in Chrome. "
            "Provide contact name and message. Optional phone number "
            "(with country code) if known."
        ),
        parameters={
            "contact": {"type": "string", "description": "Person or chat name"},
            "message": {"type": "string", "description": "Message text to send"},
            "phone": {"type": "string", "description": "Optional phone with country code"},
        },
        required=["contact"],
        risk_level=RiskLevel.SAFE,
        execute=_send_whatsapp,
    ))
