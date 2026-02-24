"""Status dashboard panel."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

from job_runner import ProgressUpdate
from gui.i18n import t


def _fmt_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "00:00"
    total = max(int(seconds), 0)
    return f"{total // 60:02d}:{total % 60:02d}"


class StatusPanel(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)

        self.workspace_var = tk.StringVar(value="-")
        self.project_var = tk.StringVar(value="-")
        self.articles_source_var = tk.StringVar(value="(default)")
        self.articles_var = tk.StringVar(value="0")
        self.yamls_var = tk.StringVar(value="0")
        self.excel_var = tk.StringVar(value="0")
        self.queue_pending_var = tk.StringVar(value="0")
        self.queue_running_var = tk.StringVar(value="0")
        self.queue_success_var = tk.StringVar(value="0")
        self.queue_failed_var = tk.StringVar(value="0")
        self.queue_cancelled_var = tk.StringVar(value="0")
        self.progress_var = tk.StringVar(value="Idle")
        self.article_counter_var = tk.StringVar(value="0/0")
        self.elapsed_var = tk.StringVar(value="00:00")

        rows = [
            (t("status.workspace"), self.workspace_var),
            (t("status.project"), self.project_var),
            (t("status.articles"), self.articles_source_var),
            (t("status.input_pdfs"), self.articles_var),
            (t("status.yaml_outputs"), self.yamls_var),
            (t("status.consolidated"), self.excel_var),
            (t("status.queue_pending"), self.queue_pending_var),
            (t("status.queue_running"), self.queue_running_var),
            (t("status.runs_success"), self.queue_success_var),
            (t("status.runs_failed"), self.queue_failed_var),
            (t("status.runs_cancelled"), self.queue_cancelled_var),
        ]

        for i, (label, variable) in enumerate(rows):
            ttk.Label(self, text=label).grid(
                row=i, column=0, sticky="w", padx=6, pady=2
            )
            ttk.Label(self, textvariable=variable).grid(
                row=i, column=1, sticky="w", padx=6, pady=2
            )

        progress_row = len(rows)
        ttk.Separator(self, orient="horizontal").grid(
            row=progress_row,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=6,
            pady=(6, 4),
        )

        ttk.Label(self, text=t("status.progress")).grid(
            row=progress_row + 1,
            column=0,
            sticky="w",
            padx=6,
            pady=(2, 1),
        )
        ttk.Label(self, textvariable=self.progress_var).grid(
            row=progress_row + 1,
            column=1,
            sticky="w",
            padx=6,
            pady=(2, 1),
        )

        self._progress_canvas = tk.Canvas(
            self,
            width=220,
            height=18,
            bg="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#808080",
            relief="sunken",
            borderwidth=1,
        )
        self._progress_canvas.grid(
            row=progress_row + 2,
            column=0,
            columnspan=2,
            sticky="w",
            padx=6,
            pady=(2, 2),
        )
        self._segments = 20

        ttk.Label(self, text=t("status.article")).grid(
            row=progress_row + 3,
            column=0,
            sticky="w",
            padx=6,
            pady=(2, 2),
        )
        ttk.Label(self, textvariable=self.article_counter_var).grid(
            row=progress_row + 3,
            column=1,
            sticky="w",
            padx=6,
            pady=(2, 2),
        )

        ttk.Label(self, text=t("status.elapsed")).grid(
            row=progress_row + 4,
            column=0,
            sticky="w",
            padx=6,
            pady=(2, 4),
        )
        ttk.Label(self, textvariable=self.elapsed_var).grid(
            row=progress_row + 4,
            column=1,
            sticky="w",
            padx=6,
            pady=(2, 4),
        )

        self.grid_columnconfigure(1, weight=1)
        self._draw_segments(0.0)

    def set_workspace(self, workspace_root: Path | None) -> None:
        self.workspace_var.set(str(workspace_root) if workspace_root else "-")

    def set_project(
        self, project_root: Path | None, articles_dir: Path | None = None
    ) -> None:
        self.project_var.set(str(project_root) if project_root else "-")
        if project_root is None:
            self.articles_source_var.set("(default)")
            self.articles_var.set("0")
            self.yamls_var.set("0")
            self.excel_var.set("0")
            return

        effective_dir = articles_dir or (project_root / "inputs" / "articles")
        is_external = articles_dir is not None
        if is_external:
            self.articles_source_var.set(f"{effective_dir} {t('status.external')}")
        else:
            self.articles_source_var.set(t("status.default_articles"))

        articles = list(effective_dir.glob("*.pdf")) if effective_dir.exists() else []
        yamls = list((project_root / "outputs" / "yamls").glob("*.yaml"))
        excel = list((project_root / "outputs" / "consolidated").glob("*.xlsx"))
        self.articles_var.set(str(len(articles)))
        self.yamls_var.set(str(len(yamls)))
        self.excel_var.set(str(len(excel)))

    def set_articles_source(self, path: str | None, *, external: bool) -> None:
        if external and path:
            self.articles_source_var.set(f"{path} (external)")
        else:
            self.articles_source_var.set("inputs/articles/ (default)")

    def update_queue_metrics(
        self, *, pending: int, running: int, success: int, failed: int, cancelled: int
    ) -> None:
        self.queue_pending_var.set(str(pending))
        self.queue_running_var.set(str(running))
        self.queue_success_var.set(str(success))
        self.queue_failed_var.set(str(failed))
        self.queue_cancelled_var.set(str(cancelled))

    def reset_progress(self) -> None:
        self.progress_var.set(t("status.idle"))
        self.article_counter_var.set("0/0")
        self.elapsed_var.set("00:00")
        self._draw_segments(0.0)

    def set_elapsed(self, elapsed_seconds: float) -> None:
        self.elapsed_var.set(_fmt_elapsed(elapsed_seconds))

    def update_progress(self, update: ProgressUpdate) -> None:
        if update.elapsed_seconds is not None:
            self.elapsed_var.set(_fmt_elapsed(update.elapsed_seconds))

        if update.article_current is not None and update.article_total is not None:
            self.article_counter_var.set(f"{update.article_current}/{update.article_total}")
            self.progress_var.set(
                t("status.article_n_of_m", current=update.article_current, total=update.article_total)
            )
            ratio = 0.0
            if update.article_total > 0:
                ratio = update.article_current / update.article_total
            self._draw_segments(ratio)

        if update.step_current is not None:
            if update.step_total:
                self.progress_var.set(
                    t("status.step_n_of_m", current=update.step_current, total=update.step_total)
                )
            else:
                self.progress_var.set(t("status.step_n", current=update.step_current))

    def _draw_segments(self, ratio: float) -> None:
        self._progress_canvas.delete("all")
        ratio = max(0.0, min(1.0, ratio))
        filled = int(round(self._segments * ratio))

        x = 2
        width = 9
        gap = 1
        for index in range(self._segments):
            color = "#003399" if index < filled else "#E0E0E0"
            self._progress_canvas.create_rectangle(
                x,
                2,
                x + width,
                15,
                fill=color,
                outline="#808080",
            )
            x += width + gap
