"""Win98-style About dialog."""

from __future__ import annotations

import tkinter as tk

from version import __version__, __build_date__


def show_about_dialog(parent: tk.Misc) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title("About SAEC")
    dialog.configure(bg="#C0C0C0")
    dialog.resizable(False, False)

    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(parent)
    dialog.grab_set()

    body = tk.Frame(dialog, bg="#C0C0C0", padx=14, pady=12)
    body.pack(fill="both", expand=True)

    tk.Label(
        body,
        text="SAEC",
        font=("MS Sans Serif", 12, "bold"),
        bg="#C0C0C0",
        anchor="w",
    ).pack(fill="x")

    tk.Label(
        body,
        text="Sistema Autonomo de Extracao CIMO para Oleo & Gas",
        bg="#C0C0C0",
        anchor="w",
    ).pack(fill="x", pady=(2, 8))

    tk.Label(
        body,
        text=(
            f"Version: {__version__}\n"
            f"Build Date: {__build_date__}\n"
            "Author: Leonardo\n"
            "Institution: Programa de Mestrado\n"
            "Stack: Python, Tkinter, PyInstaller, Ollama"
        ),
        justify="left",
        anchor="w",
        bg="#C0C0C0",
    ).pack(fill="x")

    button_row = tk.Frame(dialog, bg="#C0C0C0", padx=12, pady=10)
    button_row.pack(fill="x")

    tk.Button(
        button_row,
        text="OK",
        width=10,
        command=dialog.destroy,
        bg="#C0C0C0",
    ).pack(side="right")

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

