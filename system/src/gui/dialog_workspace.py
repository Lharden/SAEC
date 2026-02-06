"""Workspace selection dialog helpers."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog


def choose_workspace(parent: tk.Misc, initial_dir: Path | None = None) -> Path | None:
    selected = filedialog.askdirectory(
        parent=parent,
        title="Select SAEC workspace",
        initialdir=str(initial_dir) if initial_dir else None,
        mustexist=False,
    )
    if not selected:
        return None
    return Path(selected).resolve()
