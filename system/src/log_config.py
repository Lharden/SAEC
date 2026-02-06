"""Logging configuration for the SAEC-O&G desktop application."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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

    # Remove existing handlers to avoid duplicates on reconfiguration
    root.handlers.clear()

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
        root.addHandler(file_handler)

    # GUI handler
    if gui_callback is not None:
        gui_handler = GUILogHandler(gui_callback)
        gui_handler.setFormatter(formatter)
        gui_handler.setLevel(level)
        root.addHandler(gui_handler)

    # Stderr handler as fallback
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.WARNING)
    root.addHandler(stream_handler)
