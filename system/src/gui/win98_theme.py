"""Win98-inspired theme helpers for Tkinter/ttk."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


WIN98_COLORS = {
    "bg": "#C0C0C0",
    "face": "#C0C0C0",
    "highlight": "#FFFFFF",
    "shadow": "#808080",
    "dark_shadow": "#404040",
    "text": "#000000",
    "selection": "#000080",
    "selection_text": "#FFFFFF",
}


def apply_win98_theme(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)

    preferred = "classic"
    if preferred in style.theme_names():
        style.theme_use(preferred)

    root.configure(background=WIN98_COLORS["bg"])

    style.configure(
        ".",
        background=WIN98_COLORS["face"],
        foreground=WIN98_COLORS["text"],
        fieldbackground=WIN98_COLORS["highlight"],
        font=("MS Sans Serif", 8),
        borderwidth=1,
        relief="flat",
    )

    style.configure("TFrame", background=WIN98_COLORS["face"])
    style.configure(
        "TLabel", background=WIN98_COLORS["face"], foreground=WIN98_COLORS["text"]
    )
    style.configure("TButton", padding=2, relief="raised")
    style.map(
        "TButton",
        background=[
            ("pressed", WIN98_COLORS["shadow"]),
            ("active", WIN98_COLORS["highlight"]),
        ],
        foreground=[
            ("pressed", WIN98_COLORS["text"]),
            ("active", WIN98_COLORS["text"]),
        ],
    )

    style.configure(
        "TEntry",
        fieldbackground=WIN98_COLORS["highlight"],
        borderwidth=1,
        relief="sunken",
    )
    style.configure(
        "TCombobox", fieldbackground=WIN98_COLORS["highlight"], borderwidth=1
    )
    style.configure("TNotebook", background=WIN98_COLORS["face"], borderwidth=1)
    style.configure("TNotebook.Tab", padding=(8, 2), background=WIN98_COLORS["face"])
    style.map(
        "TNotebook.Tab",
        background=[
            ("selected", WIN98_COLORS["highlight"]),
            ("active", WIN98_COLORS["face"]),
        ],
        foreground=[("selected", WIN98_COLORS["text"])],
    )

    style.configure(
        "Status.TLabel",
        background=WIN98_COLORS["face"],
        foreground=WIN98_COLORS["text"],
        relief="sunken",
        padding=(4, 2),
    )
    style.configure(
        "Section.TLabelframe",
        background=WIN98_COLORS["face"],
        borderwidth=1,
        relief="groove",
    )
    style.configure(
        "Section.TLabelframe.Label",
        background=WIN98_COLORS["face"],
        foreground=WIN98_COLORS["text"],
    )
    return style
