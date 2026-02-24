"""Win98-style tooltip helper."""

from __future__ import annotations

import tkinter as tk


class Tooltip:
    def __init__(self, widget: tk.Misc, text: str, *, delay_ms: int = 500) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None

        widget.bind("<Enter>", self._on_enter, add=True)
        widget.bind("<Leave>", self._on_leave, add=True)
        widget.bind("<ButtonPress>", self._on_leave, add=True)

    def _on_enter(self, _event: object) -> None:
        self._schedule()

    def _on_leave(self, _event: object) -> None:
        self._cancel_schedule()
        self._hide()

    def _schedule(self) -> None:
        self._cancel_schedule()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_schedule(self) -> None:
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self) -> None:
        if self._window is not None:
            return

        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.attributes("-topmost", True)

        label = tk.Label(
            self._window,
            text=self.text,
            justify="left",
            bg="#FFFFE1",
            fg="#000000",
            relief="solid",
            borderwidth=1,
            wraplength=300,
            padx=4,
            pady=2,
            font=("MS Sans Serif", 8),
        )
        label.pack()

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._window.geometry(f"+{x}+{y}")

    def _hide(self) -> None:
        if self._window is None:
            return
        self._window.destroy()
        self._window = None


def add_tooltip(widget: tk.Misc, text: str, *, delay_ms: int = 500) -> Tooltip:
    return Tooltip(widget, text, delay_ms=delay_ms)
