"""Centralized application version metadata."""

from __future__ import annotations

__version__ = "1.0.0"
__build_date__ = "2026-02-17"


def version_label() -> str:
    return f"{__version__} ({__build_date__})"
