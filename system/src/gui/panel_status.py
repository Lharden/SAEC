"""Status dashboard panel."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk


class StatusPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self.workspace_var = tk.StringVar(value="-")
        self.project_var = tk.StringVar(value="-")
        self.articles_var = tk.StringVar(value="0")
        self.yamls_var = tk.StringVar(value="0")
        self.excel_var = tk.StringVar(value="0")
        self.queue_pending_var = tk.StringVar(value="0")
        self.queue_running_var = tk.StringVar(value="0")
        self.queue_success_var = tk.StringVar(value="0")
        self.queue_failed_var = tk.StringVar(value="0")
        self.queue_cancelled_var = tk.StringVar(value="0")

        rows = [
            ("Workspace", self.workspace_var),
            ("Project", self.project_var),
            ("Input PDFs", self.articles_var),
            ("YAML outputs", self.yamls_var),
            ("Consolidated files", self.excel_var),
            ("Queue pending", self.queue_pending_var),
            ("Queue running", self.queue_running_var),
            ("Runs success", self.queue_success_var),
            ("Runs failed", self.queue_failed_var),
            ("Runs cancelled", self.queue_cancelled_var),
        ]

        for i, (label, variable) in enumerate(rows):
            ttk.Label(self, text=f"{label}:").grid(
                row=i, column=0, sticky="w", padx=6, pady=2
            )
            ttk.Label(self, textvariable=variable).grid(
                row=i, column=1, sticky="w", padx=6, pady=2
            )

        self.grid_columnconfigure(1, weight=1)

    def set_workspace(self, workspace_root: Path | None) -> None:
        self.workspace_var.set(str(workspace_root) if workspace_root else "-")

    def set_project(self, project_root: Path | None) -> None:
        self.project_var.set(str(project_root) if project_root else "-")
        if project_root is None:
            self.articles_var.set("0")
            self.yamls_var.set("0")
            self.excel_var.set("0")
            return

        articles = list((project_root / "inputs" / "articles").glob("*.pdf"))
        yamls = list((project_root / "outputs" / "yamls").glob("*.yaml"))
        excel = list((project_root / "outputs" / "consolidated").glob("*.xlsx"))
        self.articles_var.set(str(len(articles)))
        self.yamls_var.set(str(len(yamls)))
        self.excel_var.set(str(len(excel)))

    def update_queue_metrics(
        self, *, pending: int, running: int, success: int, failed: int, cancelled: int
    ) -> None:
        self.queue_pending_var.set(str(pending))
        self.queue_running_var.set(str(running))
        self.queue_success_var.set(str(success))
        self.queue_failed_var.set(str(failed))
        self.queue_cancelled_var.set(str(cancelled))
