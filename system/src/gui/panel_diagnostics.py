"""Diagnostics panel with runtime health checks."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from gui.tooltip import add_tooltip
from health_check import HealthCheckResult


class DiagnosticsPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_run_checks: Callable[[], list[HealthCheckResult]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_run_checks = on_run_checks

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)
        run_button = ttk.Button(toolbar, text="Run Checks", command=self.refresh)
        run_button.pack(side="left")
        add_tooltip(run_button, "Run runtime diagnostics checks")

        columns = ("check", "status", "details")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        self._tree.heading("check", text="Check")
        self._tree.heading("status", text="Status")
        self._tree.heading("details", text="Details")
        self._tree.column("check", width=180, anchor="w")
        self._tree.column("status", width=80, anchor="center")
        self._tree.column("details", width=560, anchor="w")

        self._tree.tag_configure("OK", foreground="#006400")
        self._tree.tag_configure("WARN", foreground="#8B6508")
        self._tree.tag_configure("FAIL", foreground="#8B0000")

        ybar = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=ybar.set)

        self._tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        ybar.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def set_run_callback(
        self, callback: Callable[[], list[HealthCheckResult]] | None
    ) -> None:
        self._on_run_checks = callback

    def set_results(self, results: list[HealthCheckResult]) -> None:
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)

        for result in results:
            self._tree.insert(
                "",
                "end",
                values=(result.name, result.status, result.details),
                tags=(result.status,),
            )

    def refresh(self) -> None:
        if self._on_run_checks is None:
            return
        results = self._on_run_checks()
        self.set_results(results)
