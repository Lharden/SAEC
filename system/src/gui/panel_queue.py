"""Queue/history panel for phase-2 execution flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from error_classifier import classify_error, ClassifiedError
from run_queue import QueueItem


class QueuePanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        # Per-job captured output lines for error classification
        self._job_outputs: dict[str, list[str]] = {}
        # Map iid -> (job_id, status, return_code) for selection lookup
        self._job_meta: dict[str, tuple[str, str, int | None]] = {}

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
        self._tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        self._tree.heading("job", text="Job")
        self._tree.heading("status", text="Status")
        self._tree.heading("mode", text="Mode")
        self._tree.heading("step", text="Step")
        self._tree.heading("article", text="Article")
        self._tree.heading("created", text="Created")
        self._tree.heading("finished", text="Finished")
        self._tree.heading("code", text="Code")

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
            wraplength=400,
            anchor="w",
            justify="left",
            padx=6,
            pady=4,
        )
        self._error_label.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4)
        )
        self._error_label.grid_remove()  # Hidden by default

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Bind selection event
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

    def refresh(self, items: list[QueueItem]) -> None:
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
            self._job_meta[iid] = (item.job_id, item.status, item.return_code)

    # ------------------------------------------------------------------
    # Error classification helpers
    # ------------------------------------------------------------------

    def record_output(self, job_id: str, line: str) -> None:
        """Append a stdout/stderr line to the per-job output buffer."""
        self._job_outputs.setdefault(job_id, []).append(line)

    def get_error_summary(self, job_id: str, return_code: int | None) -> str:
        """Classify the error for *job_id* and return a formatted string."""
        lines = self._job_outputs.get(job_id, [])
        result: ClassifiedError = classify_error(
            output_lines=lines, return_code=return_code
        )
        if result.suggestion:
            return f"{result.message}\n{result.suggestion}"
        return result.message

    def _on_select(self, _event: object) -> None:
        """Show classified error when a failed/cancelled job is selected."""
        selection = self._tree.selection()
        if not selection:
            self._error_label.grid_remove()
            return

        iid = selection[0]
        meta = self._job_meta.get(iid)
        if meta is None:
            self._error_label.grid_remove()
            return

        job_id, status, return_code = meta
        if status in ("failed", "cancelled"):
            summary = self.get_error_summary(job_id, return_code)
            self._error_label.configure(text=summary)
            self._error_label.grid()
        else:
            self._error_label.configure(text="")
            self._error_label.grid_remove()
