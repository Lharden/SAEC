"""Pipeline run/cancel controller for the SAEC GUI."""

from __future__ import annotations

import logging
import time
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

from job_runner import ProgressUpdate, RunResult
from safety_policy import SafetyConfirmation, evaluate_safety

if TYPE_CHECKING:
    from gui.app import SAECWin98App


_RUN_ERROR_FIX_HINTS: list[tuple[str, str]] = [
    (
        "No PDF files found in inputs/articles/",
        "Copy at least one .pdf into the selected project's inputs/articles folder and press F5.",
    ),
    (
        "Mapping file not found",
        "Run Step 1 for this project to generate mapping.csv.",
    ),
    (
        "Mapping file is empty",
        "Run Step 1 for this project to regenerate mapping.csv.",
    ),
    (
        "Mapping is out of date",
        "Run Step 1 for this project to sync mapping.csv with current PDFs.",
    ),
    (
        "Step 3 requires ingest outputs",
        "Run Step 2 first to create outputs/work/<ART_ID>/hybrid.json.",
    ),
    (
        "Project profile is not configured.",
        "Open Project > Configure Profile and save an active profile for this project.",
    ),
    (
        "local_only preset requires Ollama connectivity.",
        "Start Ollama (ollama serve) or choose a preset that can use API providers.",
    ),
    (
        "Project is required.",
        "Select a project in the Project dropdown or create one with New....",
    ),
    (
        "Selected project path does not exist.",
        "Re-select a valid workspace/project in the GUI.",
    ),
    (
        "Workspace path does not exist.",
        "Select an existing workspace folder.",
    ),
]


def _fmt_elapsed(seconds: float) -> str:
    total = max(int(seconds), 0)
    return f"{total // 60:02d}:{total % 60:02d}"


class PipelineController:
    """Handles run/cancel pipeline, progress, safety confirmations, mapping autofix."""

    def __init__(self, app: SAECWin98App) -> None:
        self._app = app
        self._logger = logging.getLogger("saec.gui.pipeline")

    # ------------------------------------------------------------------
    # Validation and blockers
    # ------------------------------------------------------------------

    def _collect_run_blockers(self, request) -> tuple[list[str], list[SafetyConfirmation]]:
        app = self._app
        errors = app.layout.run_panel.validate(
            workspace_root=app.workspace_root,
            project_root=app.project_root,
        )

        if (
            request.mode == "all"
            and not app._ollama_available
            and app.layout.run_panel.preset_var.get() == "local_only"
        ):
            errors.append("local_only preset requires Ollama connectivity.")

        safety = evaluate_safety(
            request, project_root=app.project_root, articles_dir=app._effective_articles_dir()
        )
        errors.extend(safety.blocking_errors)

        unique: list[str] = []
        seen: set[str] = set()
        for err in errors:
            clean = err.strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            unique.append(clean)

        return unique, safety.confirmations

    @staticmethod
    def _run_error_hint(error: str) -> str:
        for snippet, hint in _RUN_ERROR_FIX_HINTS:
            if snippet in error:
                return hint
        return "Open Help > Help and Troubleshooting for guided recovery steps."

    def _show_run_blocked_popup(self, errors: list[str]) -> None:
        lines = [
            "The run cannot start yet. Fix the following item(s):",
            "",
        ]
        for idx, error in enumerate(errors, start=1):
            lines.append(f"{idx}. {error}")
            lines.append(f"   Fix: {self._run_error_hint(error)}")
            lines.append("")
        messagebox.showerror("Run blocked", "\n".join(lines).rstrip(), parent=self._app)

    def _attempt_mapping_autofix(self, errors: list[str]) -> bool:
        app = self._app
        if app.project_root is None:
            return False
        if not any(err.startswith("Mapping") for err in errors):
            return False

        confirm = messagebox.askyesno(
            "Fix Mapping",
            (
                "The project mapping is missing, empty, or out of date.\n\n"
                "Do you want SAEC to sync mapping.csv automatically now?"
            ),
            parent=app,
        )
        if not confirm:
            return False

        try:
            from config import generate_mapping_csv

            articles_dir = app._effective_articles_dir() or (
                app.project_root / "inputs" / "articles"
            )
            mapping_path = app.project_root / "mapping.csv"
            generate_mapping_csv(
                articles_dir=articles_dir,
                output_path=mapping_path,
                overwrite=False,
            )
        except Exception as exc:
            messagebox.showerror(
                "Mapping fix failed",
                (
                    "Automatic mapping sync failed.\n"
                    f"Reason: {exc}\n\n"
                    "Use Step 1 for this project and retry."
                ),
                parent=app,
            )
            return False

        app.layout.status_panel.set_project(
            app.project_root, articles_dir=app._effective_articles_dir()
        )
        app.layout.outputs_panel.refresh()
        app.layout.status_var.set("Project mapping synchronized.")
        messagebox.showinfo(
            "Mapping fixed",
            "mapping.csv was synchronized successfully. You can run again now.",
            parent=app,
        )
        return True

    # ------------------------------------------------------------------
    # Run / cancel
    # ------------------------------------------------------------------

    def on_run(self) -> None:
        app = self._app
        if app.project_root is None:
            messagebox.showwarning(
                "Project required", "Select or create a project first.", parent=app
            )
            return

        if app._runner.main_script is not None and not app._runner.main_script.exists():
            messagebox.showerror(
                "Runner error",
                f"Pipeline entrypoint not found: {app._runner.main_script}",
                parent=app,
            )
            return

        request = app.layout.run_panel.build_request(
            workspace_root=app.workspace_root,
            project_root=app.project_root,
            articles_path=app._articles_override,
        )

        errors, confirmations = self._collect_run_blockers(request)
        if errors:
            app.layout.run_panel.show_validation_errors(errors)
            if self._attempt_mapping_autofix(errors):
                errors, confirmations = self._collect_run_blockers(request)
                app.layout.run_panel.show_validation_errors(errors)
            if errors:
                self._show_run_blocked_popup(errors)
                return

        app.layout.run_panel.show_validation_errors([])

        if not self._confirm_safety_prompts(confirmations):
            return

        item = app._queue.enqueue(request)
        self._logger.info(
            "[queue] queued job=%s mode=%s article=%s",
            item.job_id,
            item.request.mode,
            item.request.article_id or "-",
        )
        app._refresh_queue_ui()
        self.start_next_if_idle()

    def _confirm_safety_prompts(self, prompts: list[SafetyConfirmation]) -> bool:
        for prompt in prompts:
            if prompt.key in self._app._suppressed_confirmations:
                continue
            accepted, suppress = self._ask_safety_confirmation(prompt)
            if suppress:
                self._app._suppressed_confirmations.add(prompt.key)
            if not accepted:
                return False
        return True

    def _ask_safety_confirmation(self, prompt: SafetyConfirmation) -> tuple[bool, bool]:
        app = self._app
        dialog = tk.Toplevel(app)
        dialog.title(prompt.title)
        dialog.configure(bg="#C0C0C0")
        dialog.resizable(False, False)
        dialog.transient(app)
        dialog.grab_set()

        accepted = False
        suppress_var = tk.BooleanVar(value=False)

        body = tk.Frame(dialog, bg="#C0C0C0", padx=12, pady=12)
        body.pack(fill="both", expand=True)

        icon_bitmap = "warning" if prompt.severity == "danger" else "question"
        tk.Label(body, bitmap=icon_bitmap, bg="#C0C0C0").pack(side="left", padx=(0, 10))
        tk.Label(
            body,
            text=prompt.message,
            bg="#C0C0C0",
            justify="left",
            wraplength=420,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        tk.Checkbutton(
            dialog,
            text="Don't ask again this session",
            variable=suppress_var,
            bg="#C0C0C0",
            anchor="w",
        ).pack(fill="x", padx=12)

        buttons = tk.Frame(dialog, bg="#C0C0C0", padx=12, pady=10)
        buttons.pack(fill="x")

        def _yes() -> None:
            nonlocal accepted
            accepted = True
            dialog.destroy()

        def _no() -> None:
            dialog.destroy()

        tk.Button(buttons, text="Yes", width=10, command=_yes, bg="#C0C0C0").pack(side="right")
        tk.Button(buttons, text="No", width=10, command=_no, bg="#C0C0C0").pack(
            side="right", padx=(0, 6)
        )

        dialog.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - dialog.winfo_width()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.wait_window()

        return accepted, bool(suppress_var.get())

    def on_cancel(self) -> None:
        app = self._app
        app._runner.cancel()
        cancelled = app._queue.cancel_running()
        if cancelled is not None:
            self._logger.info("[queue] cancelled job=%s", cancelled.job_id)
        app.layout.status_var.set("Cancelling...")
        app._refresh_queue_ui()
        app._refresh_enabled_states()
        app.after(10, self.start_next_if_idle)

    def on_cancel_job(self, job_id: str) -> None:
        if self._app._running_job_id != job_id:
            return
        self.on_cancel()

    # ------------------------------------------------------------------
    # Runner callbacks
    # ------------------------------------------------------------------

    def on_runner_output(self, line: str) -> None:
        app = self._app
        job_id = app._running_job_id
        if job_id is not None:
            current_job_id = str(job_id)
            try:
                def _enqueue_output(jid: str = current_job_id, ln: str = line) -> None:
                    app.layout.queue_panel.record_output(jid, ln)

                app.after(0, _enqueue_output)
            except tk.TclError:
                pass
        self._logger.info("%s", line)

    def on_runner_progress(self, update: ProgressUpdate) -> None:
        self._app.after(0, lambda: self._apply_runner_progress(update))

    def _apply_runner_progress(self, update: ProgressUpdate) -> None:
        app = self._app
        app.layout.status_panel.update_progress(update)
        if update.article_current is not None and update.article_total is not None:
            app.layout.status_article_var.set(
                f"Article {update.article_current}/{update.article_total}"
            )
        if update.elapsed_seconds is not None:
            app.layout.status_elapsed_var.set(f"Elapsed {_fmt_elapsed(update.elapsed_seconds)}")

    def on_runner_complete(self, result: RunResult) -> None:
        app = self._app

        def _done() -> None:
            finished = app._queue.finish_running(result)
            app._running_job_id = None

            app._stop_elapsed_updates()
            app.layout.status_panel.set_project(
                app.project_root, articles_dir=app._effective_articles_dir()
            )
            app.layout.outputs_panel.refresh()

            if finished is not None:
                self._logger.info(
                    "[queue] finished job=%s status=%s code=%s",
                    finished.job_id,
                    finished.status,
                    finished.return_code,
                )

            if result.return_code == -2:
                app.layout.status_var.set("Run timed out.")
            elif result.success:
                app.layout.status_var.set("Run completed successfully.")
            else:
                app.layout.status_var.set(f"Run failed (code={result.return_code}).")

            app.layout.run_panel.set_running(False)
            app._refresh_queue_ui()
            app._refresh_enabled_states()
            app._save_queue_history()
            app._notify_job_completion(success=result.success)
            self.start_next_if_idle()

        app.after(0, _done)

    # ------------------------------------------------------------------
    # Queue idle starter
    # ------------------------------------------------------------------

    def start_next_if_idle(self) -> None:
        app = self._app
        if app._runner.is_running:
            return
        next_item = app._queue.start_next()
        if next_item is None:
            app._refresh_enabled_states()
            return

        app._running_job_id = next_item.job_id
        app._run_started_at = time.monotonic()
        app.layout.status_article_var.set("Article 0/0")
        app.layout.status_elapsed_var.set("Elapsed 00:00")
        app.layout.status_panel.reset_progress()
        app._schedule_elapsed_updates()

        app.layout.run_panel.set_running(True)
        app.layout.status_var.set(f"Running job {next_item.job_id}...")
        self._logger.info(
            "[queue] starting job=%s mode=%s",
            next_item.job_id,
            next_item.request.mode,
        )
        app._refresh_queue_ui()
        app._refresh_enabled_states()

        app._runner.run_async(
            next_item.request,
            on_output=self.on_runner_output,
            on_complete=self.on_runner_complete,
            on_progress=self.on_runner_progress,
        )
