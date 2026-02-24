"""Queue management and status bar helpers for the SAEC GUI."""

from __future__ import annotations

import ctypes
import logging
import os
import time
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui.app import SAECWin98App


def _fmt_elapsed(seconds: float) -> str:
    total = max(int(seconds), 0)
    return f"{total // 60:02d}:{total % 60:02d}"


class QueueController:
    """Handles queue UI refresh, history persistence, elapsed time, and notifications."""

    def __init__(self, app: SAECWin98App) -> None:
        self._app = app
        self._logger = logging.getLogger("saec.gui.queue")

    # ------------------------------------------------------------------
    # Queue UI
    # ------------------------------------------------------------------

    def refresh_queue_ui(self) -> None:
        app = self._app
        items = app._queue.snapshot()
        app.layout.queue_panel.refresh(items)

        pending = sum(1 for item in items if item.status == "pending")
        running = sum(1 for item in items if item.status == "running")
        success = sum(1 for item in items if item.status == "success")
        failed = sum(1 for item in items if item.status in ("failed", "timeout"))
        cancelled = sum(1 for item in items if item.status == "cancelled")
        app.layout.status_panel.update_queue_metrics(
            pending=pending,
            running=running,
            success=success,
            failed=failed,
            cancelled=cancelled,
        )

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------

    def save_history(self) -> None:
        app = self._app
        if app._queue_history_path is None:
            return
        try:
            app._queue.save_history(app._queue_history_path)
        except Exception as exc:
            self._logger.warning("Failed to save queue history: %s", exc)

    def load_history(self) -> None:
        app = self._app
        if app._queue_history_path is None:
            return
        try:
            app._queue.load_history(app._queue_history_path)
        except Exception as exc:
            self._logger.warning("Failed to load queue history: %s", exc)

    # ------------------------------------------------------------------
    # Elapsed time / clock
    # ------------------------------------------------------------------

    def tick_clock(self) -> None:
        app = self._app
        app.layout.status_clock_var.set(time.strftime("%H:%M"))
        app._clock_after_id = app.after(1000, self.tick_clock)

    def schedule_elapsed_updates(self) -> None:
        self.stop_elapsed_updates()
        app = self._app

        def _tick() -> None:
            if app._run_started_at is None or not app._runner.is_running:
                return
            elapsed = time.monotonic() - app._run_started_at
            app.layout.status_panel.set_elapsed(elapsed)
            app.layout.status_elapsed_var.set(f"Elapsed {_fmt_elapsed(elapsed)}")
            app._elapsed_after_id = app.after(500, _tick)

        _tick()

    def stop_elapsed_updates(self) -> None:
        app = self._app
        if app._elapsed_after_id is not None:
            try:
                app.after_cancel(app._elapsed_after_id)
            except tk.TclError:
                pass
        app._elapsed_after_id = None
        app._run_started_at = None

    # ------------------------------------------------------------------
    # Job completion notification
    # ------------------------------------------------------------------

    def notify_job_completion(self, *, success: bool) -> None:
        app = self._app
        if not app._notify_var.get():
            return

        self._flash_taskbar()

        if os.name == "nt":
            try:
                import winsound

                winsound.MessageBeep(
                    winsound.MB_ICONASTERISK if success else winsound.MB_ICONHAND
                )
            except Exception:
                pass

    def _flash_taskbar(self) -> None:
        if os.name != "nt":
            return
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            hwnd = self._app.winfo_id()

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_uint),
                    ("hwnd", ctypes.c_void_p),
                    ("dwFlags", ctypes.c_uint),
                    ("uCount", ctypes.c_uint),
                    ("dwTimeout", ctypes.c_uint),
                ]

            info = FLASHWINFO(
                ctypes.sizeof(FLASHWINFO),
                hwnd,
                0x00000003,
                3,
                0,
            )
            user32.FlashWindowEx(ctypes.byref(info))
        except Exception:
            pass
