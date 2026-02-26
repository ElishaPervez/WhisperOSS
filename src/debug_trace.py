import json
import logging
from pathlib import Path
from typing import Any, Optional


_LOGGER_NAME = "whispeross.widget_debug"
_DEFAULT_PATH = Path(__file__).resolve().parents[1] / "debug.txt"
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
