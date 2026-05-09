import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional


_LOGGER_NAME = "whispeross.widget_debug"


def _default_debug_path() -> Path:
    # When bundled by PyInstaller, __file__ lives inside a temp _MEIPASS folder
    # (onefile) or inside the _internal/ dir (onedir). Neither is a good place
    # to write debug.txt. Prefer next to the exe if writable, else %APPDATA%.
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        try:
            probe = exe_dir / ".whispeross_write_probe"
            probe.touch(exist_ok=True)
            probe.unlink(missing_ok=True)
            return exe_dir / "debug.txt"
        except OSError:
            app_data = os.getenv("APPDATA")
            base = Path(app_data) / "WhisperOSS" if app_data else Path.home() / ".whispeross"
            base.mkdir(parents=True, exist_ok=True)
            return base / "debug.txt"
    return Path(__file__).resolve().parents[1] / "debug.txt"


_DEFAULT_PATH = _default_debug_path()
_initialized = False
_current_path: Optional[Path] = None


def _normalize_text(value: Any, max_len: int = 280) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    collapsed = " ".join(text.split()).replace("|", "/")
    if len(collapsed) > max_len:
        return collapsed[: max_len - 3] + "..."
    return collapsed


def _build_logger(path: Path) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    resolved = path.resolve()
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            try:
                if Path(handler.baseFilename).resolve() == resolved:
                    return logger
            except Exception:
                pass
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    file_handler = logging.FileHandler(resolved, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.addHandler(file_handler)
    return logger


def configure_debug_trace(log_path: Optional[str] = None) -> Path:
    global _initialized, _current_path

    path = Path(log_path).expanduser() if log_path else _DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    logger = _build_logger(path)
    resolved = path.resolve()
    if (not _initialized) or (_current_path is None) or (_current_path != resolved):
        logger.info("event=debug_trace_initialized | trigger=configure_debug_trace | reason=debug tracing enabled | path=%s", _normalize_text(resolved))
    _initialized = True
    _current_path = resolved
    return resolved


def trace_widget_event(
    event: str,
    *,
    trigger: str = "",
    reason: str = "",
    **details: Any,
) -> None:
    if not _initialized:
        configure_debug_trace()

    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        configure_debug_trace()
        logger = logging.getLogger(_LOGGER_NAME)

    fields = [f"event={_normalize_text(event)}"]
    if trigger:
        fields.append(f"trigger={_normalize_text(trigger)}")
    if reason:
        fields.append(f"reason={_normalize_text(reason)}")
    for key, value in details.items():
        fields.append(f"{_normalize_text(key)}={_normalize_text(value)}")
    logger.info(" | ".join(fields))
