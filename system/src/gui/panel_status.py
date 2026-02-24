"""Status dashboard panel with modern progress bar."""

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
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _fmt_eta(elapsed: float, current: int, total: int) -> str:
    """Estimate remaining time from elapsed, current, total."""
    if current <= 0 or total <= 0 or elapsed <= 0:
        return "--:--"
    rate = elapsed / current
    remaining = rate * (total - current)
    return _fmt_elapsed(remaining)


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
        self.progress_var = tk.StringVar(value=t("status.idle"))
        self.article_counter_var = tk.StringVar(value="0/0")
        self.elapsed_var = tk.StringVar(value="00:00")

        # --- Project info section ---
        info_frame = ttk.LabelFrame(self, text=t("status.project"))
        info_frame.pack(fill="x", padx=4, pady=(4, 2))

        info_rows = [
            (t("status.workspace"), self.workspace_var),
            (t("status.articles"), self.articles_source_var),
            (t("status.input_pdfs"), self.articles_var),
            (t("status.yaml_outputs"), self.yamls_var),
            (t("status.consolidated"), self.excel_var),
        ]

        for i, (label, variable) in enumerate(info_rows):
            ttk.Label(info_frame, text=label, font=("Segoe UI", 8)).grid(
                row=i, column=0, sticky="w", padx=6, pady=1
            )
            ttk.Label(info_frame, textvariable=variable, font=("Segoe UI", 8)).grid(
                row=i, column=1, sticky="w", padx=6, pady=1
            )
        info_frame.grid_columnconfigure(1, weight=1)

        # --- Queue stats ---
        queue_frame = ttk.LabelFrame(self, text=t("queue.tab"))
        queue_frame.pack(fill="x", padx=4, pady=2)

        queue_rows = [
            (t("status.queue_pending"), self.queue_pending_var),
            (t("status.runs_success"), self.queue_success_var),
            (t("status.runs_failed"), self.queue_failed_var),
        ]
        for i, (label, variable) in enumerate(queue_rows):
            ttk.Label(queue_frame, text=label, font=("Segoe UI", 8)).grid(
                row=i, column=0, sticky="w", padx=6, pady=1
            )
            ttk.Label(queue_frame, textvariable=variable, font=("Segoe UI", 8)).grid(
                row=i, column=1, sticky="w", padx=6, pady=1
            )
        queue_frame.grid_columnconfigure(1, weight=1)

        # --- Progress section (the main feature) ---
        progress_frame = ttk.LabelFrame(self, text=t("status.progress"))
        progress_frame.pack(fill="x", padx=4, pady=(2, 4))

        # Progress bar
        self._progress_value = tk.DoubleVar(value=0.0)
        self._progressbar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            variable=self._progress_value,
            maximum=100,
        )
        self._progressbar.pack(fill="x", padx=8, pady=(6, 2))

        # Percentage + time row
        time_row = ttk.Frame(progress_frame)
        time_row.pack(fill="x", padx=8, pady=(0, 2))

        self._pct_var = tk.StringVar(value="0%")
        ttk.Label(time_row, textvariable=self._pct_var, font=("Segoe UI", 9, "bold")).pack(
            side="left"
        )

        self._eta_var = tk.StringVar(value="")
        ttk.Label(time_row, textvariable=self._eta_var, font=("Segoe UI", 8), foreground="#666").pack(
            side="right"
        )

        self._elapsed_label_var = tk.StringVar(value="")
        ttk.Label(time_row, textvariable=self._elapsed_label_var, font=("Segoe UI", 8), foreground="#666").pack(
            side="right", padx=(0, 12)
        )

        # "Article X/Y" row
        article_row = ttk.Frame(progress_frame)
        article_row.pack(fill="x", padx=8, pady=(0, 2))

        ttk.Label(article_row, textvariable=self.progress_var, font=("Segoe UI", 8)).pack(
            side="left"
        )
        ttk.Label(article_row, textvariable=self.article_counter_var, font=("Segoe UI", 8)).pack(
            side="right"
        )

        # Last activity line
        self._activity_var = tk.StringVar(value="")
        activity_label = ttk.Label(
            progress_frame,
            textvariable=self._activity_var,
            font=("Segoe UI", 8),
            foreground="#444",
            wraplength=260,
        )
        activity_label.pack(fill="x", padx=8, pady=(0, 6))

        self._last_elapsed: float = 0.0
        self._last_current: int = 0
        self._last_total: int = 0

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
        self._progress_value.set(0.0)
        self._pct_var.set("0%")
        self._eta_var.set("")
        self._elapsed_label_var.set("")
        self._activity_var.set("")
        self._last_elapsed = 0.0
        self._last_current = 0
        self._last_total = 0

    def set_elapsed(self, elapsed_seconds: float) -> None:
        self.elapsed_var.set(_fmt_elapsed(elapsed_seconds))
        self._last_elapsed = elapsed_seconds
        self._elapsed_label_var.set(f"⏱ {_fmt_elapsed(elapsed_seconds)}")
        # Update ETA if we have article counts
        if self._last_total > 0 and self._last_current > 0:
            eta = _fmt_eta(elapsed_seconds, self._last_current, self._last_total)
            self._eta_var.set(f"≈ {eta} restante")

    def update_progress(self, update: ProgressUpdate) -> None:
        if update.elapsed_seconds is not None:
            self.set_elapsed(update.elapsed_seconds)

        if update.article_current is not None and update.article_total is not None:
            current = update.article_current
            total = update.article_total
            self._last_current = current
            self._last_total = total

            self.article_counter_var.set(f"{current}/{total}")
            self.progress_var.set(
                t("status.article_n_of_m", current=current, total=total)
            )

            pct = (current / total * 100) if total > 0 else 0
            self._progress_value.set(pct)
            self._pct_var.set(f"{pct:.0f}%")

            if update.elapsed_seconds and current > 0:
                eta = _fmt_eta(update.elapsed_seconds, current, total)
                self._eta_var.set(f"≈ {eta} restante")

        if update.step_current is not None:
            if update.step_total:
                self.progress_var.set(
                    t("status.step_n_of_m", current=update.step_current, total=update.step_total)
                )
            else:
                self.progress_var.set(t("status.step_n", current=update.step_current))

        if update.last_activity:
            self._activity_var.set(update.last_activity)
