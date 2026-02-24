"""Helpers for resolving bundled vs development resource paths."""

from __future__ import annotations

from pathlib import Path
import sys


def get_resource_path(relative_path: str | Path) -> Path:
    """Resolve a resource path for both dev and bundled modes.

    In development, resources are resolved from the ``system`` directory.
    In PyInstaller bundles, resources are resolved from ``sys._MEIPASS``.
    """
    rel = Path(relative_path)
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        return (Path(bundle_root) / rel).resolve()
    dev_root = Path(__file__).resolve().parents[1]
    return (dev_root / rel).resolve()
