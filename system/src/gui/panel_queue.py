"""Queue/history panel for desktop execution flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from error_classifier import ClassifiedError, classify_error
from gui.tooltip import add_tooltip
from gui.i18n import t
from run_queue import QueueItem

MAX_OUTPUT_LINES_PER_JOB = 500


class QueuePanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self._on_view_logs: Callable[[str], None] | None = None
        self._on_cancel_job: Callable[[str], None] | None = None

        # Per-job captured output lines for error classification
        self._job_outputs: dict[str, list[str]] = {}
        # Map iid -> (job_id, status, return_code, command)
        self._job_meta: dict[str, tuple[str, str, int | None, list[str] | None]] = {}

        self._status_icons = self._build_status_icons()

        columns = (
            "job",
            "status",
            "mode",
            "step",
            "article",
            "created",
            "finished",
            "code",
        )
        self._tree = ttk.Treeview(
            self,
            columns=columns,
            show="tree headings",
            height=14,
        )
        self._tree.heading("job", text=t("queue.col_job"))
        self._tree.heading("status", text=t("queue.col_status"))
        self._tree.heading("mode", text=t("queue.col_mode"))
        self._tree.heading("step", text=t("queue.col_step"))
        self._tree.heading("article", text=t("queue.col_article"))
        self._tree.heading("created", text=t("queue.col_created"))
        self._tree.heading("finished", text=t("queue.col_finished"))
        self._tree.heading("code", text=t("queue.col_code"))

        self._tree.column("#0", width=24, anchor="center")
        self._tree.column("job", width=90, anchor="w")
        self._tree.column("status", width=90, anchor="w")
        self._tree.column("mode", width=70, anchor="w")
        self._tree.column("step", width=60, anchor="center")
        self._tree.column("article", width=120, anchor="w")
        self._tree.column("created", width=165, anchor="w")
        self._tree.column("finished", width=165, anchor="w")
        self._tree.column("code", width=60, anchor="center")

        ybar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=ybar.set)

        self._tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        ybar.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)

        # Error info label shown when a failed/cancelled job is selected
        self._error_label = tk.Label(
            self,
            text="",
            fg="#CC0000",
            bg="#C0C0C0",
            wraplength=520,
            anchor="w",
            justify="left",
            padx=6,
            pady=4,
        )
        self._error_label.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4)
        )
        self._error_label.grid_remove()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Button-3>", self._on_context_menu)
        add_tooltip(self._tree, t("queue.tooltip"))

        self._menu = tk.Menu(self, tearoff=False)
        self._menu.add_command(label=t("queue.view_logs"), command=self._view_logs_selected)
        self._menu.add_command(
            label=t("queue.copy_command"), command=self._copy_command_selected
        )
        self._menu.add_command(label=t("queue.cancel_job"), command=self._cancel_selected)

    def set_callbacks(
        self,
        *,
        on_view_logs: Callable[[str], None] | None = None,
        on_cancel_job: Callable[[str], None] | None = None,
    ) -> None:
        self._on_view_logs = on_view_logs
        self._on_cancel_job = on_cancel_job

    def refresh(self, items: list[QueueItem]) -> None:
        active_job_ids = {item.job_id for item in items}
        stale_job_ids = [
            job_id for job_id in self._job_outputs if job_id not in active_job_ids
        ]
        for job_id in stale_job_ids:
            self._job_outputs.pop(job_id, None)

        self._job_meta.clear()
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)

        for item in items:
            step = "" if item.request.step is None else str(item.request.step)
            article = item.request.article_id or "-"
            finished = item.finished_at or ""
            code = "" if item.return_code is None else str(item.return_code)
            iid = self._tree.insert(
                "",
                "end",
                text="",
                image=self._status_icons.get(item.status, self._status_icons["pending"]),
                values=(
                    item.job_id,
                    item.status,
                    item.request.mode,
                    step,
                    article,
                    item.created_at,
                    finished,
                    code,
                ),
            )
            self._job_meta[iid] = (item.job_id, item.status, item.return_code, item.command)

    # ------------------------------------------------------------------
    # Error classification helpers
    # ------------------------------------------------------------------

    def record_output(self, job_id: str, line: str) -> None:
        """Append a stdout/stderr line to the per-job output buffer."""
        lines = self._job_outputs.setdefault(job_id, [])
        lines.append(line)
        if len(lines) > MAX_OUTPUT_LINES_PER_JOB:
            del lines[:-MAX_OUTPUT_LINES_PER_JOB]

    def get_error_summary(self, job_id: str, return_code: int | None) -> str:
        """Classify the error for *job_id* and return a formatted string."""
        lines = self._job_outputs.get(job_id, [])
        result: ClassifiedError = classify_error(
            output_lines=lines, return_code=return_code
        )
        if result.suggestion:
            return f"{result.message}\n{result.suggestion}"
        return result.message

    def _selected_meta(self) -> tuple[str, str, int | None, list[str] | None] | None:
        selection = self._tree.selection()
        if not selection:
            return None
        return self._job_meta.get(selection[0])

    def _on_select(self, _event: object) -> None:
        """Show classified error when a failed/cancelled job is selected."""
        meta = self._selected_meta()
        if meta is None:
            self._error_label.grid_remove()
            return

        job_id, status, return_code, _command = meta
        if status in ("failed", "cancelled", "timeout"):
            summary = self.get_error_summary(job_id, return_code)
            self._error_label.configure(text=summary)
            self._error_label.grid()
        else:
            self._error_label.configure(text="")
            self._error_label.grid_remove()

    def _view_logs_selected(self) -> None:
        meta = self._selected_meta()
        if meta is None:
            return
        job_id, _status, _return_code, _command = meta
        if self._on_view_logs is not None:
            self._on_view_logs(job_id)

    def _copy_command_selected(self) -> None:
        meta = self._selected_meta()
        if meta is None:
            return
        _job_id, _status, _return_code, command = meta
        if not command:
            return
        self.clipboard_clear()
        self.clipboard_append(" ".join(command))

    def _cancel_selected(self) -> None:
        meta = self._selected_meta()
        if meta is None:
            return
        job_id, status, _return_code, _command = meta
        if status != "running":
            return
        if self._on_cancel_job is not None:
            self._on_cancel_job(job_id)

    def _on_context_menu(self, event: tk.Event[tk.Misc]) -> None:
        row = self._tree.identify_row(event.y)
        if not row:
            return
        self._tree.selection_set(row)
        meta = self._selected_meta()
        if meta is None:
            return
        _job_id, status, _return_code, command = meta

        self._menu.entryconfigure(
            t("queue.copy_command"),
            state="normal" if command else "disabled",
        )
        self._menu.entryconfigure(
            t("queue.cancel_job"),
            state="normal" if status == "running" else "disabled",
        )
        self._menu.tk_popup(event.x_root, event.y_root)

    def _build_status_icons(self) -> dict[str, tk.PhotoImage]:
        def _icon(color: str) -> tk.PhotoImage:
            img = tk.PhotoImage(width=16, height=16)
            img.put("#C0C0C0", to=(0, 0, 16, 16))
            img.put(color, to=(4, 4, 12, 12))
            return img

        return {
            "pending": _icon("#808080"),
            "running": _icon("#003399"),
            "success": _icon("#228B22"),
            "failed": _icon("#B22222"),
            "cancelled": _icon("#8B4513"),
            "timeout": _icon("#CC6600"),
        }
