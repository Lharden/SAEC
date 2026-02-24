"""Win98-style toolbar with code-generated 16x16 icons."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable


@dataclass
class Toolbar:
    frame: ttk.Frame
    buttons: dict[str, tk.Button]
    icons: list[tk.PhotoImage]


def _draw_rect(icon: tk.PhotoImage, x0: int, y0: int, x1: int, y1: int, color: str) -> None:
    icon.put(color, to=(x0, y0, x1, y1))


def _new_icon() -> tk.PhotoImage:
    icon = tk.PhotoImage(width=16, height=16)
    icon.put("#C0C0C0", to=(0, 0, 16, 16))
    return icon


def _icon_play() -> tk.PhotoImage:
    icon = _new_icon()
    for i in range(8):
        _draw_rect(icon, 4 + i, 3 + i // 2, 5 + i, 13 - i // 2, "#008000")
    return icon


def _icon_stop() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 4, 4, 12, 12, "#AA0000")
    return icon


def _icon_refresh() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 3, 6, 12, 8, "#003399")
    _draw_rect(icon, 8, 3, 10, 12, "#003399")
    _draw_rect(icon, 11, 5, 14, 8, "#003399")
    return icon


def _icon_folder() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 2, 6, 14, 13, "#C9A400")
    _draw_rect(icon, 2, 4, 8, 7, "#E6C74A")
    return icon


def _icon_gear() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 6, 6, 10, 10, "#5A5A5A")
    _draw_rect(icon, 7, 3, 9, 6, "#5A5A5A")
    _draw_rect(icon, 7, 10, 9, 13, "#5A5A5A")
    _draw_rect(icon, 3, 7, 6, 9, "#5A5A5A")
    _draw_rect(icon, 10, 7, 13, 9, "#5A5A5A")
    return icon


def _icon_help() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 6, 3, 10, 6, "#003399")
    _draw_rect(icon, 9, 6, 11, 8, "#003399")
    _draw_rect(icon, 7, 8, 9, 10, "#003399")
    _draw_rect(icon, 7, 12, 9, 14, "#003399")
    return icon


def _icon_new() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 4, 2, 12, 13, "#FFFFFF")
    _draw_rect(icon, 4, 2, 12, 3, "#808080")
    _draw_rect(icon, 4, 12, 12, 13, "#808080")
    return icon


def _icon_magnifier() -> tk.PhotoImage:
    icon = _new_icon()
    _draw_rect(icon, 4, 4, 9, 9, "#003399")
    _draw_rect(icon, 8, 8, 12, 12, "#003399")
    return icon


def build_toolbar(
    parent: tk.Misc,
    *,
    on_run: Callable[[], None],
    on_cancel: Callable[[], None],
    on_refresh: Callable[[], None],
    on_workspace: Callable[[], None],
    on_settings: Callable[[], None],
    on_help: Callable[[], None],
    on_new_project: Callable[[], None],
    on_diagnostics: Callable[[], None],
) -> Toolbar:
    frame = ttk.Frame(parent, relief="raised", borderwidth=1)

    icon_map = {
        "run": _icon_play(),
        "cancel": _icon_stop(),
        "refresh": _icon_refresh(),
        "workspace": _icon_folder(),
        "settings": _icon_gear(),
        "help": _icon_help(),
        "new": _icon_new(),
        "diag": _icon_magnifier(),
    }

    button_specs: list[tuple[str, Callable[[], None], str]] = [
        ("run", on_run, "Run"),
        ("cancel", on_cancel, "Cancel"),
        ("refresh", on_refresh, "Refresh"),
        ("workspace", on_workspace, "Workspace"),
        ("new", on_new_project, "New"),
        ("diag", on_diagnostics, "Diagnostics"),
        ("settings", on_settings, "Settings"),
        ("help", on_help, "Help"),
    ]

    buttons: dict[str, tk.Button] = {}
    for i, (key, callback, tooltip) in enumerate(button_specs):
        btn = tk.Button(
            frame,
            image=icon_map[key],
            command=callback,
            relief="raised",
            bg="#C0C0C0",
            activebackground="#D8D8D8",
            width=24,
            height=22,
        )
        btn.grid(row=0, column=i, padx=(2 if i else 4, 2), pady=2)
        btn.configure(takefocus=0)
        btn._tooltip_text = tooltip  # type: ignore[attr-defined]
        buttons[key] = btn

    return Toolbar(frame=frame, buttons=buttons, icons=list(icon_map.values()))
