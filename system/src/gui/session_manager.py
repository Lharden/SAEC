"""Session persistence for the SAEC GUI."""

from __future__ import annotations

import logging
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui.app import SAECWin98App


class SessionManager:
    """Handles session restore, persist, and close logic."""

    def __init__(self, app: SAECWin98App) -> None:
        self._app = app
        self._logger = logging.getLogger("saec.gui.session")

    def restore(self) -> None:
        app = self._app
        settings = app._settings_store.load()
        app._notify_var.set(bool(settings.get("notify_on_completion", True)))
        recent = settings.get("recent_workspaces", [])
        app.layout.workspace_combo.configure(values=recent)

        selected_preset = settings.get("selected_preset", "pilot")
        if selected_preset in {"pilot", "batch", "local_only", "api_only"}:
            app.layout.run_panel.preset_var.set(selected_preset)
            app.layout.run_panel._on_preset_changed()  # noqa: SLF001

        saved_geometry = settings.get("window_geometry", "")
        if saved_geometry:
            try:
                app.geometry(saved_geometry)
            except tk.TclError:
                pass

        active_tab = settings.get("active_tab", 0)
        try:
            app.layout.right_notebook.select(active_tab)
        except (tk.TclError, IndexError):
            pass

        app._set_main_sash_position(int(settings.get("main_sash_position", 320)))

        last_workspace = settings.get("last_workspace", "")
        if last_workspace:
            candidate = Path(last_workspace)
            if candidate.exists():
                app._set_workspace(candidate)

    def persist(self) -> None:
        app = self._app
        data = app._settings_store.load()
        data["selected_preset"] = app.layout.run_panel.preset_var.get()
        data["notify_on_completion"] = bool(app._notify_var.get())
        app._settings_store.save(data)

    def on_close(self) -> None:
        app = self._app

        if app._runner.is_running:
            confirm = messagebox.askyesno(
                "Pipeline Running",
                "A pipeline job is still running.\nCancel the job and quit?",
                parent=app,
            )
            if not confirm:
                return
            app._runner.cancel()
            deadline = time.monotonic() + 5.0
            while app._runner.is_running and time.monotonic() < deadline:
                app.update()
                time.sleep(0.1)

        pending = app._queue.pending_count
        if pending > 0:
            confirm = messagebox.askyesno(
                "Pending Jobs",
                f"{pending} job(s) still pending in the queue.\nQuit anyway?",
                parent=app,
            )
            if not confirm:
                return

        app._save_queue_history()
        self.persist()

        try:
            app._settings_store.save_window_state(
                geometry=app.geometry(),
                active_tab=app.layout.right_notebook.index("current"),
                main_sash_position=app._get_main_sash_position(),
            )
        except Exception:
            pass

        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass

        if app._elapsed_after_id is not None:
            app.after_cancel(app._elapsed_after_id)
        if app._clock_after_id is not None:
            app.after_cancel(app._clock_after_id)

        app.destroy()
