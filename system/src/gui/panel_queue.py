"""Queue/history panel for phase-2 execution flow."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from run_queue import QueueItem


class QueuePanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

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
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def refresh(self, items: list[QueueItem]) -> None:
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)

        for item in items:
            step = "" if item.request.step is None else str(item.request.step)
            article = item.request.article_id or "-"
            finished = item.finished_at or ""
            code = "" if item.return_code is None else str(item.return_code)
            self._tree.insert(
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
