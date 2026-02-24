"""Main shell layout for the Win98-style desktop app."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from gui.panel_diagnostics import DiagnosticsPanel
from gui.panel_logs import LogsPanel
from gui.panel_outputs import OutputsPanel
from gui.panel_profile import ProfilePanel
from gui.panel_queue import QueuePanel
from gui.panel_run import RunPanel
from gui.panel_status import StatusPanel
from gui.i18n import t


@dataclass
class MainLayout:
    workspace_combo: ttk.Combobox
    project_combo: ttk.Combobox
    browse_workspace_button: ttk.Button
    new_project_button: ttk.Button
    articles_entry: ttk.Entry
    articles_path_var: tk.StringVar
    browse_articles_button: ttk.Button
    clear_articles_button: ttk.Button
    run_panel: RunPanel
    queue_panel: QueuePanel
    outputs_panel: OutputsPanel
    logs_panel: LogsPanel
    diagnostics_panel: DiagnosticsPanel
    profile_panel: ProfilePanel
    status_panel: StatusPanel
    status_var: tk.StringVar
    status_article_var: tk.StringVar
    status_elapsed_var: tk.StringVar
    status_clock_var: tk.StringVar
    right_notebook: ttk.Notebook
    body_paned: tk.PanedWindow


def _status_cell(parent: tk.Misc, variable: tk.StringVar, *, width: int) -> ttk.Label:
    return ttk.Label(
        parent,
        textvariable=variable,
        style="Status.TLabel",
        anchor="w",
        width=width,
    )


def build_main_layout(root: tk.Tk, *, on_run, on_cancel) -> MainLayout:
    container = ttk.Frame(root)
    container.pack(fill="both", expand=True)

    top = ttk.Frame(container)
    top.pack(fill="x", padx=6, pady=6)

    ttk.Label(top, text=t("layout.workspace")).grid(
        row=0, column=0, sticky="w", padx=(0, 4), pady=2
    )
    workspace_combo = ttk.Combobox(top, width=58, state="readonly")
    workspace_combo.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=2)
    browse_workspace_button = ttk.Button(top, text=t("layout.browse"))
    browse_workspace_button.grid(row=0, column=2, sticky="w", padx=(0, 8), pady=2)

    ttk.Label(top, text=t("layout.project")).grid(
        row=1, column=0, sticky="w", padx=(0, 4), pady=2
    )
    project_combo = ttk.Combobox(top, width=28, state="readonly")
    project_combo.grid(row=1, column=1, sticky="w", padx=(0, 4), pady=2)
    new_project_button = ttk.Button(top, text=t("layout.new"))
    new_project_button.grid(row=1, column=2, sticky="w", pady=2)

    ttk.Label(top, text=t("layout.articles")).grid(
        row=2, column=0, sticky="w", padx=(0, 4), pady=2
    )
    articles_path_var = tk.StringVar(value="(default)")
    articles_entry = ttk.Entry(top, textvariable=articles_path_var, width=58, state="readonly")
    articles_entry.grid(row=2, column=1, sticky="ew", padx=(0, 4), pady=2)
    articles_btn_frame = ttk.Frame(top)
    articles_btn_frame.grid(row=2, column=2, sticky="w", pady=2)
    browse_articles_button = ttk.Button(articles_btn_frame, text=t("layout.browse"))
    browse_articles_button.pack(side="left")
    clear_articles_button = ttk.Button(articles_btn_frame, text=t("layout.clear"))
    clear_articles_button.pack(side="left", padx=(4, 0))

    top.grid_columnconfigure(1, weight=1)

    body = tk.PanedWindow(
        container,
        orient=tk.HORIZONTAL,
        sashrelief=tk.RAISED,
        sashwidth=8,
        showhandle=True,
        handlesize=8,
        handlepad=3,
        bd=1,
        relief=tk.SUNKEN,
        background="#C0C0C0",
    )
    body.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    left = ttk.Frame(body)
    right = ttk.Frame(body)
    body.add(left, minsize=280, stretch="never")
    body.add(right, minsize=400, stretch="always")

    run_panel = RunPanel(left, on_run=on_run, on_cancel=on_cancel)
    run_panel.pack(fill="x", pady=(0, 6))

    status_panel = StatusPanel(left)
    status_panel.pack(fill="x")

    notebook = ttk.Notebook(right)
    notebook.pack(fill="both", expand=True)

    outputs_panel = OutputsPanel(notebook)
    queue_panel = QueuePanel(notebook)
    logs_panel = LogsPanel(notebook)
    diagnostics_panel = DiagnosticsPanel(notebook)
    profile_panel = ProfilePanel(notebook)
    notebook.add(queue_panel, text=t("queue.tab"))
    notebook.add(outputs_panel, text=t("outputs.tab"))
    notebook.add(logs_panel, text=t("logs.tab"))
    notebook.add(diagnostics_panel, text=t("diagnostics.tab"))
    notebook.add(profile_panel, text=t("profile.tab"))

    status_var = tk.StringVar(value="Ready")
    status_article_var = tk.StringVar(value="0/0")
    status_elapsed_var = tk.StringVar(value="00:00")
    status_clock_var = tk.StringVar(value="--:--")

    status_bar = ttk.Frame(container)
    status_bar.pack(fill="x", padx=6, pady=(0, 6))

    _status_cell(status_bar, status_var, width=70).pack(side="left", fill="x", expand=True)
    _status_cell(status_bar, status_article_var, width=14).pack(side="left", padx=(4, 0))
    _status_cell(status_bar, status_elapsed_var, width=14).pack(side="left", padx=(4, 0))
    _status_cell(status_bar, status_clock_var, width=8).pack(side="left", padx=(4, 0))

    return MainLayout(
        workspace_combo=workspace_combo,
        project_combo=project_combo,
        browse_workspace_button=browse_workspace_button,
        new_project_button=new_project_button,
        articles_entry=articles_entry,
        articles_path_var=articles_path_var,
        browse_articles_button=browse_articles_button,
        clear_articles_button=clear_articles_button,
        run_panel=run_panel,
        queue_panel=queue_panel,
        outputs_panel=outputs_panel,
        logs_panel=logs_panel,
        diagnostics_panel=diagnostics_panel,
        profile_panel=profile_panel,
        status_panel=status_panel,
        status_var=status_var,
        status_article_var=status_article_var,
        status_elapsed_var=status_elapsed_var,
        status_clock_var=status_clock_var,
        right_notebook=notebook,
        body_paned=body,
    )
