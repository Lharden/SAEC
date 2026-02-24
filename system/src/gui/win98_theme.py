"""Modern flat theme for SAEC (replaces Win98 aesthetic)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#F0F0F0",
    "surface": "#FFFFFF",
    "text": "#1A1A2E",
    "text_secondary": "#6C6C80",
    "border": "#D1D5DB",
    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "success": "#059669",
    "error": "#DC2626",
    "selection": "#2563EB",
    "selection_text": "#FFFFFF",
    "tab_active": "#FFFFFF",
    "tab_inactive": "#E5E7EB",
    "progressbar": "#2563EB",
}

_FONT = ("Segoe UI", 9)
_FONT_SMALL = ("Segoe UI", 8)
_FONT_BOLD = ("Segoe UI", 9, "bold")
_FONT_HEADING = ("Segoe UI", 10, "bold")


def apply_win98_theme(root: tk.Tk) -> ttk.Style:
    """Apply a modern flat theme. Keeps the same function name for compatibility."""
    style = ttk.Style(root)

    # Use clam as base — clean, flat look on Windows
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=COLORS["bg"])

    style.configure(
        ".",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["surface"],
        font=_FONT,
        borderwidth=0,
        relief="flat",
    )

    style.configure("TFrame", background=COLORS["bg"])
    style.configure(
        "TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=_FONT,
    )

    # Buttons — subtle rounded look
    style.configure(
        "TButton",
        padding=(10, 4),
        relief="flat",
        background=COLORS["surface"],
        borderwidth=1,
        font=_FONT,
    )
    style.map(
        "TButton",
        background=[
            ("pressed", COLORS["border"]),
            ("active", COLORS["tab_inactive"]),
            ("disabled", COLORS["bg"]),
        ],
        foreground=[
            ("disabled", COLORS["text_secondary"]),
        ],
    )

    # Primary action button
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground=COLORS["selection_text"],
        padding=(12, 5),
        font=_FONT_BOLD,
    )
    style.map(
        "Accent.TButton",
        background=[
            ("pressed", COLORS["accent_hover"]),
            ("active", COLORS["accent_hover"]),
        ],
    )

    # Entries
    style.configure(
        "TEntry",
        fieldbackground=COLORS["surface"],
        borderwidth=1,
        relief="solid",
        padding=4,
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["surface"],
        borderwidth=1,
    )

    # Notebook tabs
    style.configure(
        "TNotebook",
        background=COLORS["bg"],
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        padding=(14, 5),
        background=COLORS["tab_inactive"],
        font=_FONT,
    )
    style.map(
        "TNotebook.Tab",
        background=[
            ("selected", COLORS["tab_active"]),
            ("active", COLORS["border"]),
        ],
        foreground=[("selected", COLORS["accent"])],
    )

    # Status bar
    style.configure(
        "Status.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["text_secondary"],
        padding=(6, 3),
        font=_FONT_SMALL,
    )

    # LabelFrame sections
    style.configure(
        "TLabelframe",
        background=COLORS["bg"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=_FONT_BOLD,
    )
    style.configure(
        "Section.TLabelframe",
        background=COLORS["bg"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Section.TLabelframe.Label",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=_FONT_BOLD,
    )

    # Treeview
    style.configure(
        "Treeview",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["surface"],
        font=_FONT,
        rowheight=24,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=_FONT_BOLD,
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["selection"])],
        foreground=[("selected", COLORS["selection_text"])],
    )

    # Progressbar — blue accent
    style.configure(
        "TProgressbar",
        background=COLORS["progressbar"],
        troughcolor=COLORS["border"],
        borderwidth=0,
        thickness=8,
    )

    # Separator
    style.configure(
        "TSeparator",
        background=COLORS["border"],
    )

    # Checkbutton
    style.configure(
        "TCheckbutton",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=_FONT,
    )

    # Scrollbar
    style.configure(
        "TScrollbar",
        background=COLORS["border"],
        troughcolor=COLORS["bg"],
        borderwidth=0,
    )

    return style
