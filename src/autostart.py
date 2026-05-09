"""Manage Windows 'Run on startup' registration via HKCU\\...\\Run.

Per-user only — matches the per-user installer scope, so no admin needed.
Dev runs (non-frozen) are intentionally not registered: the registry would
point at python.exe + a path inside the working tree, which is brittle and
not what end users want anyway. The config flag still persists in dev so
toggling state survives a fresh frozen install.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "WhisperOSS"


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _executable_command() -> str | None:
    """Return the quoted command to launch WhisperOSS, or None in dev mode."""
    if not _is_frozen():
        return None
    exe = Path(sys.executable).resolve()
    return f'"{exe}"'


def _open_registry():
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None
    return winreg


def is_enabled() -> bool:
    """True iff the Run-key entry exists AND points to the current executable.

    A stale entry from an older install location counts as 'not enabled' so
    that the next reconcile rewrites it.
    """
    winreg = _open_registry()
    if winreg is None:
        return False
    expected = _executable_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("autostart: failed to read Run key: %s", exc)
        return False
    if expected is None:
        # Dev mode: any registered value counts as 'enabled' for UI purposes.
        return bool(value)
    return str(value).strip().lower() == expected.lower()


def enable() -> bool:
    """Register WhisperOSS to launch at user logon. Returns True on success."""
    command = _executable_command()
    if command is None:
        logger.info("autostart.enable: skipped (running from source, not a frozen build)")
        return False
    winreg = _open_registry()
    if winreg is None:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, command)
        logger.info("autostart: registered Run key -> %s", command)
        return True
    except OSError as exc:
        logger.warning("autostart: failed to write Run key: %s", exc)
        return False


def disable() -> bool:
    """Remove the Run-key entry. Returns True on success or if absent."""
    winreg = _open_registry()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        logger.info("autostart: removed Run key")
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        logger.warning("autostart: failed to remove Run key: %s", exc)
        return False


def reconcile(desired: bool) -> None:
    """Make the Run key match `desired`. Safe to call on every startup."""
    if desired:
        if not is_enabled():
            enable()
    else:
        if is_enabled():
            disable()
