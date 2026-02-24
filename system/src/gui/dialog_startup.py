"""Startup dialog for selecting project mode."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from gui.i18n import t


def prompt_startup_choice(
    parent: tk.Misc,
    recent_workspaces: list[str],
) -> tuple[str, Path | None] | None:
    """
    Show startup dialog to choose between new or existing project.

    Returns:
        ("new", workspace_path) or ("existing", workspace_path) or None if cancelled
    """
    dialog = tk.Toplevel(parent)
    dialog.title(t("startup.title"))
    dialog.configure(bg="#C0C0C0")
    dialog.resizable(False, False)

    if isinstance(parent, (tk.Tk, tk.Toplevel)):
        dialog.transient(parent)
    dialog.grab_set()

    result: tuple[str, Path | None] | None = None

    container = tk.Frame(dialog, bg="#C0C0C0", padx=20, pady=20)
    container.pack(fill="both", expand=True)

    # Title
    tk.Label(
        container,
        text=t("startup.welcome"),
        font=("MS Sans Serif", 12, "bold"),
        bg="#C0C0C0",
    ).pack(pady=(0, 10))

    tk.Label(
        container,
        text=t("startup.choose"),
        bg="#C0C0C0",
    ).pack(pady=(0, 20))

    # Recent workspaces frame
    recent_frame = ttk.LabelFrame(container, text=t("startup.recent"), padding=10)
    recent_frame.pack(fill="x", pady=(0, 10))

    workspace_var = tk.StringVar()
    if recent_workspaces:
        workspace_var.set(recent_workspaces[0])
        recent_combo = ttk.Combobox(
            recent_frame,
            textvariable=workspace_var,
            values=recent_workspaces,
            width=50,
            state="readonly",
        )
        recent_combo.pack(fill="x")
    else:
        tk.Label(
            recent_frame,
            text=t("startup.no_recent"),
            bg="#C0C0C0",
            fg="#666666",
        ).pack()

    # Buttons frame
    buttons_frame = tk.Frame(container, bg="#C0C0C0")
    buttons_frame.pack(fill="x", pady=20)

    def on_new_project():
        nonlocal result
        ws = workspace_var.get()
        if ws:
            result = ("new", Path(ws))
        else:
            result = ("new", None)
        dialog.destroy()

    def on_continue_project():
        nonlocal result
        ws = workspace_var.get()
        if not ws and not recent_workspaces:
            messagebox.showwarning(
                t("startup.workspace_required"),
                t("startup.select_workspace_first"),
                parent=dialog,
            )
            return
        result = ("existing", Path(ws) if ws else None)
        dialog.destroy()

    def on_browse_workspace():
        selected = filedialog.askdirectory(
            parent=dialog,
            title=t("project.select_workspace"),
        )
        if selected:
            workspace_var.set(selected)
            if recent_workspaces:
                recent_combo.configure(values=[selected] + recent_workspaces)

    # New project button
    tk.Button(
        buttons_frame,
        text=t("startup.new_project"),
        command=on_new_project,
        bg="#C0C0C0",
        width=20,
        height=2,
    ).pack(side="left", padx=5)

    # Continue button
    tk.Button(
        buttons_frame,
        text=t("startup.continue_project"),
        command=on_continue_project,
        bg="#C0C0C0",
        width=20,
        height=2,
    ).pack(side="left", padx=5)

    # Browse button
    tk.Button(
        buttons_frame,
        text=t("startup.browse"),
        command=on_browse_workspace,
        bg="#C0C0C0",
        width=15,
        height=2,
    ).pack(side="left", padx=5)

    # Cancel button
    tk.Button(
        container,
        text=t("startup.cancel"),
        command=dialog.destroy,
        bg="#C0C0C0",
    ).pack(pady=(10, 0))

    # Center dialog
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
    return result

