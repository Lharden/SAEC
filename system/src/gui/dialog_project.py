"""Project creation dialog helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog


def prompt_new_project(parent: tk.Misc) -> str | None:
    return simpledialog.askstring(
        "New Project",
        "Project name:",
        parent=parent,
    )
