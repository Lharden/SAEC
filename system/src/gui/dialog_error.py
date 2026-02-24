"""Win98-styled error dialog for unhandled exceptions."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def show_error_dialog(parent: tk.Misc, message: str, details: str = "") -> None:
    """Display a modal error dialog with optional expandable traceback.

    Args:
        parent: The parent widget (usually the root Tk window).
        message: Short user-friendly error description.
        details: Full traceback or technical details (shown in expandable area).
    """
    dialog = tk.Toplevel(parent)
    dialog.title("SAEC Error")
    dialog.configure(bg="#C0C0C0")
    dialog.resizable(False, False)

    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(parent)
    dialog.grab_set()

    # --- Top section: icon + message ---
    top_frame = tk.Frame(dialog, bg="#C0C0C0", padx=12, pady=12)
    top_frame.pack(fill=tk.X)

    icon_label = tk.Label(top_frame, bitmap="error", bg="#C0C0C0")
    icon_label.pack(side=tk.LEFT, padx=(0, 12))

    msg_label = tk.Label(
        top_frame,
        text=message,
        bg="#C0C0C0",
        fg="#000000",
        wraplength=420,
        justify=tk.LEFT,
        anchor=tk.W,
    )
    msg_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # --- Details section (only if details provided) ---
    if details:
        details_frame = tk.Frame(dialog, bg="#C0C0C0", padx=12)
        details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        details_label = tk.Label(
            details_frame,
            text="Details:",
            bg="#C0C0C0",
            fg="#000000",
            anchor=tk.W,
        )
        details_label.pack(fill=tk.X, pady=(0, 4))

        text_frame = tk.Frame(details_frame, bg="#C0C0C0")
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Courier New", 8),
            bg="#FFFFFF",
            fg="#000000",
            width=72,
            height=12,
            state=tk.NORMAL,
            yscrollcommand=scrollbar.set,
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=text_widget.yview)

        text_widget.insert(tk.END, details)
        text_widget.configure(state=tk.DISABLED)

    # --- Button bar ---
    button_frame = tk.Frame(dialog, bg="#C0C0C0", padx=12)
    button_frame.pack(fill=tk.X, pady=(4, 12))

    def _copy_to_clipboard() -> None:
        full_text = f"{message}\n\n{details}" if details else message
        dialog.clipboard_clear()
        dialog.clipboard_append(full_text)

    if details:
        copy_btn = tk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=_copy_to_clipboard,
            bg="#C0C0C0",
            fg="#000000",
            width=16,
        )
        copy_btn.pack(side=tk.LEFT)

    ok_btn = tk.Button(
        button_frame,
        text="OK",
        command=dialog.destroy,
        bg="#C0C0C0",
        fg="#000000",
        width=10,
    )
    ok_btn.pack(side=tk.RIGHT)

    # Center on parent
    dialog.update_idletasks()
    dw = dialog.winfo_width()
    dh = dialog.winfo_height()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dialog.geometry(f"+{x}+{y}")

    dialog.wait_window()

