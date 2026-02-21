"""Application context and logging setup."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

try:
    from .config import Paths, LLMConfig, ExtractionConfig
except (ImportError, ModuleNotFoundError):  # pragma: no cover - standalone usage
    from config import Paths, LLMConfig, ExtractionConfig


class _DefaultArtigoIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "artigo_id"):
            record.artigo_id = "-"
        if not hasattr(record, "provider"):
            record.provider = "-"
        if not hasattr(record, "action"):
            record.action = "-"
        return True


def setup_logging(
    *,
    log_level: str = "INFO",
    log_path: Optional[Path] = None,
    console: bool = True,
) -> logging.Logger:
    """Configure a unified logger for the pipeline."""
    logger = logging.getLogger("saec")

    if logger.handlers:
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        return logger

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(artigo_id)s | %(provider)s | %(action)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(_DefaultArtigoIdFilter())
        logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(_DefaultArtigoIdFilter())
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger


@dataclass
class AppContext:
    """Lightweight context container for dependency injection."""

    paths: Any
    llm_config: Any
    extraction_config: Any
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("saec"))


def make_context(log_level: str = "INFO") -> AppContext:
    """Factory that builds a ready-to-use context."""
    paths = Paths()
    llm_config = LLMConfig()
    extraction_config = ExtractionConfig()

    log_path = paths.EXTRACTION / "outputs" / "saec.log"
    logger = setup_logging(log_level=log_level, log_path=log_path, console=True)

    return AppContext(
        paths=paths,
        llm_config=llm_config,
        extraction_config=extraction_config,
        logger=logger,
    )
