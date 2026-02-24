"""Logging configuration for the SAEC desktop application."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MANAGED_ATTR = "_saec_managed"
_MANAGED_KIND_ATTR = "_saec_managed_kind"


class GUILogHandler(logging.Handler):
    """Handler that forwards log records to a GUI callback via a thread-safe queue."""

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._callback(msg)
        except Exception:
            self.handleError(record)


def _mark_managed(handler: logging.Handler, kind: str) -> logging.Handler:
    setattr(handler, _MANAGED_ATTR, True)
    setattr(handler, _MANAGED_KIND_ATTR, kind)
    return handler


def _is_managed(handler: logging.Handler) -> bool:
    return bool(getattr(handler, _MANAGED_ATTR, False))


def _remove_managed_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        if not _is_managed(handler):
            continue
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            continue


def setup_logging(
    *,
    log_dir: Path | None = None,
    gui_callback: Callable[[str], None] | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure root logger with file and optional GUI handlers.

    Args:
        log_dir: Directory for log files. If None, file logging is skipped.
        gui_callback: Callback to send formatted log lines to the GUI.
        level: Minimum log level.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Replace only previously managed handlers; keep third-party handlers untouched.
    _remove_managed_handlers(root)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # File handler with rotation
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "saec-og.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(_mark_managed(file_handler, kind="file"))

    # GUI handler
    if gui_callback is not None:
        gui_handler = GUILogHandler(gui_callback)
        gui_handler.setFormatter(formatter)
        gui_handler.setLevel(level)
        root.addHandler(_mark_managed(gui_handler, kind="gui"))

    # Stderr handler as fallback
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.WARNING)
    root.addHandler(_mark_managed(stream_handler, kind="stream"))

