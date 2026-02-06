"""Main shell layout for the Win98-style desktop app."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from gui.panel_logs import LogsPanel
from gui.panel_outputs import OutputsPanel
from gui.panel_queue import QueuePanel
from gui.panel_run import RunPanel
from gui.panel_status import StatusPanel


@dataclass
class MainLayout:
    workspace_combo: ttk.Combobox
    project_combo: ttk.Combobox
    browse_workspace_button: ttk.Button
    new_project_button: ttk.Button
    run_panel: RunPanel
    queue_panel: QueuePanel
    outputs_panel: OutputsPanel
    logs_panel: LogsPanel
    status_panel: StatusPanel
    status_var: tk.StringVar


def build_main_layout(root: tk.Tk, *, on_run, on_cancel) -> MainLayout:
    container = ttk.Frame(root)
    container.pack(fill="both", expand=True)

    top = ttk.Frame(container)
    top.pack(fill="x", padx=6, pady=6)

    ttk.Label(top, text="Workspace").grid(
        row=0, column=0, sticky="w", padx=(0, 4), pady=2
    )
    workspace_combo = ttk.Combobox(top, width=58, state="readonly")
    workspace_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=2)
    browse_workspace_button = ttk.Button(top, text="Browse...")
    browse_workspace_button.grid(row=0, column=2, sticky="w", padx=(0, 8), pady=2)

    ttk.Label(top, text="Project").grid(
        row=1, column=0, sticky="w", padx=(0, 4), pady=2
    )
    project_combo = ttk.Combobox(top, width=28, state="readonly")
    project_combo.grid(row=1, column=1, sticky="w", padx=(0, 4), pady=2)
    new_project_button = ttk.Button(top, text="New...")
    new_project_button.grid(row=1, column=2, sticky="w", pady=2)

    top.grid_columnconfigure(1, weight=1)

    body = ttk.Panedwindow(container, orient="horizontal")
    body.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    left = ttk.Frame(body)
    right = ttk.Frame(body)
    body.add(left, weight=1)
    body.add(right, weight=3)

    run_panel = RunPanel(left, on_run=on_run, on_cancel=on_cancel)
    run_panel.pack(fill="x", pady=(0, 6))

    status_panel = StatusPanel(left)
    status_panel.pack(fill="x")

    notebook = ttk.Notebook(right)
    notebook.pack(fill="both", expand=True)

    outputs_panel = OutputsPanel(notebook)
    queue_panel = QueuePanel(notebook)
    logs_panel = LogsPanel(notebook)
    notebook.add(queue_panel, text="Queue")
    notebook.add(outputs_panel, text="Outputs")
    notebook.add(logs_panel, text="Logs")

    status_var = tk.StringVar(value="Ready")
    status_bar = ttk.Label(
        container, textvariable=status_var, style="Status.TLabel", anchor="w"
    )
    status_bar.pack(fill="x", padx=6, pady=(0, 6))

    return MainLayout(
        workspace_combo=workspace_combo,
        project_combo=project_combo,
        browse_workspace_button=browse_workspace_button,
        new_project_button=new_project_button,
        run_panel=run_panel,
        queue_panel=queue_panel,
        outputs_panel=outputs_panel,
        logs_panel=logs_panel,
        status_panel=status_panel,
        status_var=status_var,
    )
