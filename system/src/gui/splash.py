"""Simple Win98-style splash screen."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

try:
    from version import __version__
except Exception:  # pragma: no cover
    __version__ = "0.0.0"


def show_startup_splash(
    root: tk.Tk,
    *,
    duration_ms: int = 2000,
    reveal_root: bool = True,
    on_complete: Callable[[], None] | None = None,
) -> None:
    try:
        _show_splash(
            root,
            duration_ms=duration_ms,
            reveal_root=reveal_root,
            on_complete=on_complete,
        )
    except Exception:
        # Splash is non-critical — if it fails, just reveal the main window.
        if reveal_root:
            try:
                root.deiconify()
            except tk.TclError:
                pass
        if on_complete is not None:
            on_complete()


def _show_splash(
    root: tk.Tk,
    *,
    duration_ms: int,
    reveal_root: bool,
    on_complete: Callable[[], None] | None,
) -> None:
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#C0C0C0", relief="raised", borderwidth=2)

    body = tk.Frame(splash, bg="#C0C0C0", padx=18, pady=14)
    body.pack(fill="both", expand=True)

    tk.Label(
        body,
        text="SAEC",
        bg="#C0C0C0",
        fg="#000000",
        font=("MS Sans Serif", 14, "bold"),
    ).pack(anchor="w")
    tk.Label(
        body,
        text=f"Win98 Edition - v{__version__}",
        bg="#C0C0C0",
        fg="#000000",
        font=("MS Sans Serif", 8),
    ).pack(anchor="w", pady=(2, 10))

    canvas = tk.Canvas(
        body,
        width=280,
        height=20,
        bg="#FFFFFF",
        highlightthickness=1,
        highlightbackground="#808080",
    )
    canvas.pack(anchor="w")

    root.withdraw()
    splash.update_idletasks()
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    w = splash.winfo_width()
    h = splash.winfo_height()
    x = max((sw - w) // 2, 20)
    y = max((sh - h) // 2, 20)
    splash.geometry(f"+{x}+{y}")

    segments = 16
    segment_w = 16
    gap = 1
    step_ms = max(duration_ms // segments, 1)

    def _tick(index: int = 0) -> None:
        if index > 0:
            x0 = 2 + (index - 1) * (segment_w + gap)
            x1 = x0 + segment_w
            canvas.create_rectangle(x0, 3, x1, 17, fill="#003399", outline="#003399")

        if index < segments:
            splash.after(step_ms, lambda: _tick(index + 1))
            return

        splash.destroy()
        if reveal_root:
            root.deiconify()
        if on_complete is not None:
            on_complete()

    _tick(0)

