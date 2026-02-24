"""Win98-style desktop shell for SAEC."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, cast

from export_report import export_summary_csv, export_summary_html
from gui.i18n import t
from gui.dialog_about import show_about_dialog
from gui.dialog_error import show_error_dialog
from gui.dialog_help import show_help_dialog
from gui.layout_main import MainLayout, build_main_layout
from gui.toolbar import Toolbar, build_toolbar
from gui.tooltip import add_tooltip
from gui.session_manager import SessionManager
from gui.pipeline_controller import PipelineController
from gui.project_manager import ProjectManager
from gui.queue_controller import QueueController
from gui.win98_theme import apply_win98_theme
from health_check import HealthCheckResult, run_health_checks
from job_runner import PipelineJobRunner, resolve_cli_runner
from log_config import setup_logging
from resource_paths import get_resource_path
from run_queue import RunQueue
from settings_store import SettingsStore


class SAECWin98App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("SAEC")
        self.geometry("1180x760")
        self.minsize(1000, 640)

        apply_win98_theme(self)
        self._set_window_icon()
        self.report_callback_exception = self._on_tk_exception

        self.workspace_root: Path | None = None
        self.project_root: Path | None = None
        self._articles_override: Path | None = None
        self._project_name_to_id: dict[str, str] = {}

        self._system_root = Path(__file__).resolve().parents[2]
        self._env_path = self._system_root / ".env"

        self._settings_store = SettingsStore(Path.home() / ".SAEC")
        initial_settings = self._settings_store.load()
        self._notify_var = tk.BooleanVar(
            value=bool(initial_settings.get("notify_on_completion", True))
        )
        self._queue = RunQueue()
        self._queue_history_path: Path | None = None

        self._suppressed_confirmations: set[str] = set()
        self._running_job_id: str | None = None
        self._run_started_at: float | None = None
        self._elapsed_after_id: str | None = None
        self._clock_after_id: str | None = None
        self._ollama_available = True

        main_script = self._detect_main_script()
        if getattr(sys, "frozen", False):
            runner_executable, runner_script = resolve_cli_runner(
                gui_executable=Path(sys.executable),
                default_main=main_script,
            )
            python_executable = str(runner_executable)
            runner_main_script = runner_script
        else:
            python_executable = sys.executable
            runner_main_script = main_script

        self._runner = PipelineJobRunner(
            python_executable=python_executable,
            main_script=runner_main_script,
        )

        self._session_manager = SessionManager(self)
        self._pipeline_controller = PipelineController(self)
        self._project_manager = ProjectManager(self)
        self._queue_controller = QueueController(self)

        self._build_menu()
        self._toolbar: Toolbar = build_toolbar(
            self,
            on_run=self._on_run,
            on_cancel=self._on_cancel,
            on_refresh=self._on_refresh_outputs,
            on_workspace=self._on_browse_workspace,
            on_settings=self._open_setup_dialog,
            on_help=self._show_help,
            on_new_project=self._on_new_project,
            on_diagnostics=self._show_diagnostics_tab,
        )
        self._toolbar.frame.pack(fill="x", padx=6, pady=(0, 4))

        self.layout: MainLayout = build_main_layout(
            self, on_run=self._on_run, on_cancel=self._on_cancel
        )

        self._wire_events()
        self._bind_shortcuts()
        self._bind_tooltips()

        self.layout.queue_panel.set_callbacks(
            on_view_logs=self._on_view_job_logs,
            on_cancel_job=self._on_cancel_job,
        )
        self.layout.diagnostics_panel.set_run_callback(self._run_diagnostics_checks)
        self.layout.profile_panel.set_configure_callback(self._on_configure_profile)

        self._configure_logging(self._settings_store.base_dir / "logs")

        self._session_manager.restore()
        self._refresh_queue_ui()
        self._refresh_enabled_states()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick_clock()
        self.after(50, self._run_startup_checks)
        self.after(100, self._ensure_first_run_setup)

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _configure_logging(self, log_dir: Path) -> None:
        setup_logging(log_dir=log_dir, gui_callback=self._append_gui_log, level=logging.INFO)
        self._logger = logging.getLogger("saec.gui")

    def _set_window_icon(self) -> None:
        icon_path = get_resource_path("src/gui/resources/saec.ico")
        if not icon_path.exists():
            return
        try:
            self.iconbitmap(str(icon_path))
        except Exception:
            return

    def _append_gui_log(self, line: str) -> None:
        try:
            self.after(0, lambda: self.layout.logs_panel.append_line(line))
        except tk.TclError:
            return

    def _detect_main_script(self) -> Path:
        candidate = Path(__file__).resolve().parents[2] / "main.py"
        if candidate.exists():
            return candidate
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            bundled = Path(meipass) / "main.py"
            if bundled.exists():
                return bundled
        return candidate

    def _wire_events(self) -> None:
        self.layout.browse_workspace_button.configure(command=self._on_browse_workspace)
        self.layout.workspace_combo.bind("<<ComboboxSelected>>", self._on_workspace_selected)
        self.layout.project_combo.bind("<<ComboboxSelected>>", self._on_project_selected)
        self.layout.new_project_button.configure(command=self._on_new_project)
        self.layout.browse_articles_button.configure(command=self._on_browse_articles)
        self.layout.clear_articles_button.configure(command=self._on_clear_articles)

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-r>", self._shortcut_run)
        self.bind_all("<Control-Shift-C>", self._shortcut_cancel)
        self.bind_all("<Control-Shift-c>", self._shortcut_cancel)
        self.bind_all("<Control-l>", self._shortcut_clear_logs)
        self.bind_all("<Control-w>", self._shortcut_workspace)
        self.bind_all("<F5>", self._shortcut_refresh)
        self.bind_all("<Control-q>", self._shortcut_quit)
        self.bind_all("<F1>", self._shortcut_help)

    def _bind_tooltips(self) -> None:
        add_tooltip(self.layout.workspace_combo, t("tooltip.workspace_combo"))
        add_tooltip(self.layout.project_combo, t("tooltip.project_combo"))
        add_tooltip(self.layout.browse_workspace_button, t("tooltip.browse_workspace"))
        add_tooltip(self.layout.new_project_button, t("tooltip.new_project"))
        add_tooltip(self.layout.articles_entry, t("tooltip.articles_entry"))
        add_tooltip(self.layout.browse_articles_button, t("tooltip.browse_articles"))
        add_tooltip(self.layout.clear_articles_button, t("tooltip.clear_articles"))

        toolbar_tooltips = {
            "run": t("toolbar.run"),
            "cancel": t("toolbar.cancel"),
            "refresh": t("toolbar.refresh"),
            "workspace": t("toolbar.workspace"),
            "new": t("toolbar.new"),
            "diag": t("toolbar.diag"),
            "settings": t("toolbar.settings"),
            "help": t("toolbar.help"),
        }
        for key, button in self._toolbar.buttons.items():
            add_tooltip(button, toolbar_tooltips.get(key, key))

    def _build_menu(self) -> None:
        menu = tk.Menu(self)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label=t("menu.exit"), command=self._on_close)
        menu.add_cascade(label=t("menu.file"), menu=file_menu)

        workspace_menu = tk.Menu(menu, tearoff=False)
        workspace_menu.add_command(
            label=t("menu.select_workspace"),
            command=self._on_browse_workspace,
        )
        menu.add_cascade(label=t("menu.workspace"), menu=workspace_menu)

        project_menu = tk.Menu(menu, tearoff=False)
        project_menu.add_command(label=t("menu.new_project"), command=self._on_new_project)
        project_menu.add_command(
            label=t("menu.configure_profile"),
            command=self._on_configure_profile,
        )
        menu.add_cascade(label=t("menu.project"), menu=project_menu)

        pipeline_menu = tk.Menu(menu, tearoff=False)
        pipeline_menu.add_command(label=t("menu.run"), command=self._on_run)
        pipeline_menu.add_command(
            label=t("menu.cancel"),
            command=self._on_cancel,
        )
        pipeline_menu.add_separator()
        pipeline_menu.add_command(
            label=t("menu.export_summary"),
            command=self._on_export_summary,
        )
        menu.add_cascade(label=t("menu.pipeline"), menu=pipeline_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_command(
            label=t("menu.refresh_outputs"),
            command=self._on_refresh_outputs,
        )
        view_menu.add_command(
            label=t("menu.clear_logs"),
            command=lambda: self.layout.logs_panel.clear() if hasattr(self, "layout") else None,
        )
        view_menu.add_command(label=t("menu.diagnostics"), command=self._show_diagnostics_tab)
        view_menu.add_command(label=t("menu.profile"), command=self._show_profile_tab)
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label=t("menu.notify_completion"),
            variable=self._notify_var,
            command=self._toggle_notify_on_completion,
        )
        menu.add_cascade(label=t("menu.view"), menu=view_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(
            label=t("menu.help_troubleshooting"),
            command=self._show_help,
        )
        help_menu.add_separator()
        help_menu.add_command(label=t("menu.about"), command=self._show_about)
        menu.add_cascade(label=t("menu.help"), menu=help_menu)

        self.configure(menu=menu)

    # ------------------------------------------------------------------
    # Session and lifecycle
    # ------------------------------------------------------------------

    def _on_tk_exception(self, exc_type, exc_value, exc_tb) -> None:
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger("saec.gui").exception("Unhandled Tk callback error")
        show_error_dialog(
            self,
            message=f"An unexpected error occurred: {exc_value}",
            details=tb_text,
        )

    def _restore_session(self) -> None:
        self._session_manager.restore()

    def _persist_session_state(self) -> None:
        self._session_manager.persist()

    def _on_close(self) -> None:
        self._session_manager.on_close()

    # ------------------------------------------------------------------
    # Diagnostics and setup
    # ------------------------------------------------------------------

    def _run_startup_checks(self) -> None:
        results = self._run_diagnostics_checks()
        failed = [item for item in results if item.status == "FAIL"]
        warns = [item for item in results if item.status == "WARN"]
        if failed:
            self.layout.status_var.set(t("dialog.startup_checks_failed"))
        elif warns:
            self.layout.status_var.set(t("dialog.startup_checks_warnings"))

    def _read_env_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not self._env_path.exists():
            return values
        for raw in self._env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def _run_diagnostics_checks(self) -> list[HealthCheckResult]:
        env_values = self._read_env_values()
        ollama_url = env_values.get("OLLAMA_BASE_URL", "").strip() or "http://localhost:11434"

        results = run_health_checks(
            workspace_root=self.workspace_root,
            system_root=self._system_root,
            ollama_url=ollama_url,
        )
        self.layout.diagnostics_panel.set_results(results)

        ollama = next((item for item in results if item.name == "Ollama"), None)
        self._ollama_available = bool(ollama and ollama.status == "OK")
        return results

    def _warn_if_no_provider_ready(self, results: list[HealthCheckResult]) -> None:
        api_keys = next((item for item in results if item.name == "API keys"), None)
        ollama = next((item for item in results if item.name == "Ollama"), None)
        api_ok = bool(api_keys and api_keys.status == "OK")
        ollama_ok = bool(ollama and ollama.status == "OK")
        if api_ok or ollama_ok:
            return
        messagebox.showwarning(
            t("dialog.provider_setup_title"),
            t("dialog.provider_setup_msg"),
            parent=self,
        )

    def _show_diagnostics_tab(self) -> None:
        self.layout.right_notebook.select(3)

    def _show_profile_tab(self) -> None:
        self.layout.right_notebook.select(4)

    def _ensure_first_run_setup(self) -> None:
        self._project_manager.ensure_first_run_setup()

    def _create_new_project_with_config(self, name: str) -> None:
        self._project_manager.create_new_project_with_config(name)

    def _select_project_by_id(self, project_id: str) -> None:
        self._project_manager.select_project_by_id(project_id)

    def _open_setup_dialog(self) -> None:
        self._project_manager.open_setup_dialog()

    def _write_env_file(self, values: dict[str, str]) -> None:
        self._project_manager.write_env_file(values)

    @staticmethod
    def _write_env_to_path(env_path: Path, values: dict[str, str]) -> None:
        from gui.project_manager import ProjectManager
        ProjectManager.write_env_to_path(env_path, values)

    # ------------------------------------------------------------------
    # Workspace and project selection (delegated to ProjectManager)
    # ------------------------------------------------------------------

    def _on_browse_workspace(self) -> None:
        self._project_manager.on_browse_workspace()

    def _on_workspace_selected(self, _event=None) -> None:
        self._project_manager.on_workspace_selected(_event)

    def _set_workspace(self, workspace_root: Path) -> None:
        self._project_manager.set_workspace(workspace_root)

    def _refresh_projects(self) -> None:
        self._project_manager.refresh_projects()

    def _on_project_selected(self, _event=None) -> None:
        self._project_manager.on_project_selected(_event)

    def _select_project_from_label(self, label: str) -> None:
        self._project_manager.select_project_from_label(label)

    def _load_project_config(self) -> None:
        self._project_manager._load_project_config()

    def _ensure_project_profile_configured(self, *, interactive: bool) -> bool:
        return self._project_manager._ensure_project_profile_configured(interactive=interactive)

    def _on_configure_profile(self) -> None:
        self._project_manager.on_configure_profile()

    def _on_new_project(self) -> None:
        self._project_manager.on_new_project()

    # ------------------------------------------------------------------
    # Articles directory override (delegated to ProjectManager)
    # ------------------------------------------------------------------

    def _effective_articles_dir(self) -> Path | None:
        return self._project_manager.effective_articles_dir()

    def _on_browse_articles(self) -> None:
        self._project_manager.on_browse_articles()

    def _on_clear_articles(self) -> None:
        self._project_manager.on_clear_articles()

    # ------------------------------------------------------------------
    # Pipeline run/cancel (delegated to PipelineController)
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        self._pipeline_controller.on_run()

    def _on_cancel(self) -> None:
        self._pipeline_controller.on_cancel()

    def _on_cancel_job(self, job_id: str) -> None:
        self._pipeline_controller.on_cancel_job(job_id)

    def _start_next_if_idle(self) -> None:
        self._pipeline_controller.start_next_if_idle()

    def _refresh_queue_ui(self) -> None:
        self._queue_controller.refresh_queue_ui()

    def _save_queue_history(self) -> None:
        self._queue_controller.save_history()

    def _load_queue_history(self) -> None:
        self._queue_controller.load_history()

    def _tick_clock(self) -> None:
        self._queue_controller.tick_clock()

    def _schedule_elapsed_updates(self) -> None:
        self._queue_controller.schedule_elapsed_updates()

    def _stop_elapsed_updates(self) -> None:
        self._queue_controller.stop_elapsed_updates()

    def _set_main_sash_position(self, position: int) -> None:
        try:
            if hasattr(self.layout.body_paned, "sashpos"):
                cast(Any, self.layout.body_paned).sashpos(0, int(position))
            else:
                self.layout.body_paned.sash_place(0, int(position), 0)
        except Exception:
            pass

    def _get_main_sash_position(self) -> int:
        try:
            if hasattr(self.layout.body_paned, "sashpos"):
                return int(cast(Any, self.layout.body_paned).sashpos(0))
            coord = self.layout.body_paned.sash_coord(0)
            if isinstance(coord, tuple) and coord:
                return int(coord[0])
        except Exception:
            pass
        return 320

    # ------------------------------------------------------------------
    # Menu/toolbar actions
    # ------------------------------------------------------------------

    def _show_about(self) -> None:
        show_about_dialog(self)

    def _show_help(self) -> None:
        show_help_dialog(self)

    def _on_refresh_outputs(self) -> None:
        self.layout.outputs_panel.refresh()
        self.layout.status_panel.set_project(
            self.project_root, articles_dir=self._effective_articles_dir()
        )

    def _toggle_notify_on_completion(self) -> None:
        data = self._settings_store.load()
        data["notify_on_completion"] = bool(self._notify_var.get())
        self._settings_store.save(data)

    def _on_view_job_logs(self, job_id: str) -> None:
        self.layout.right_notebook.select(2)
        self._logger.info("[queue] viewing logs for job=%s", job_id)

    def _on_export_summary(self) -> None:
        if self.project_root is None:
            messagebox.showwarning(
                t("dialog.project_required"),
                t("dialog.select_project_first"),
                parent=self,
            )
            return

        yamls_dir = self.project_root / "outputs" / "yamls"
        if not yamls_dir.exists():
            messagebox.showwarning(
                t("dialog.no_outputs_title"),
                t("dialog.no_outputs_msg"),
                parent=self,
            )
            return
        if not any(yamls_dir.glob("*.yaml")):
            messagebox.showwarning(
                t("dialog.no_yamls_title"),
                t("dialog.no_yamls_msg"),
                parent=self,
            )
            return

        default_csv = self.project_root / "outputs" / "consolidated" / "summary_report.csv"
        target = filedialog.asksaveasfilename(
            parent=self,
            title=t("dialog.export_title"),
            defaultextension=".csv",
            initialfile=default_csv.name,
            initialdir=str(default_csv.parent),
            filetypes=[("CSV files", "*.csv")],
        )
        if not target:
            return

        csv_path = Path(target)
        count = export_summary_csv(yamls_dir, csv_path)
        self._logger.info("Exported summary CSV with %s rows: %s", count, csv_path)

        if messagebox.askyesno(
            t("dialog.export_html_title"),
            t("dialog.export_html"),
            parent=self,
        ):
            html_path = csv_path.with_suffix(".html")
            export_summary_html(yamls_dir, html_path)
            self._logger.info("Exported summary HTML: %s", html_path)

        self.layout.status_var.set(t("dialog.summary_exported", filename=csv_path.name))

    def _notify_job_completion(self, *, success: bool) -> None:
        self._queue_controller.notify_job_completion(success=success)

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------

    def _shortcut_run(self, _event=None) -> str:
        self._on_run()
        return "break"

    def _shortcut_cancel(self, _event=None) -> str:
        self._on_cancel()
        return "break"

    def _shortcut_clear_logs(self, _event=None) -> str:
        self.layout.logs_panel.clear()
        return "break"

    def _shortcut_workspace(self, _event=None) -> str:
        self._on_browse_workspace()
        return "break"

    def _shortcut_refresh(self, _event=None) -> str:
        self._on_refresh_outputs()
        return "break"

    def _shortcut_quit(self, _event=None) -> str:
        self._on_close()
        return "break"

    def _shortcut_help(self, _event=None) -> str:
        self._show_help()
        return "break"

    # ------------------------------------------------------------------
    # UI state rules
    # ------------------------------------------------------------------

    def _refresh_enabled_states(self) -> None:
        has_workspace = self.workspace_root is not None
        has_project = self.project_root is not None
        running = self._runner.is_running

        self.layout.new_project_button.configure(state="normal" if has_workspace else "disabled")
        self.layout.project_combo.configure(state="readonly" if has_workspace else "disabled")

        articles_state = "normal" if has_project and not running else "disabled"
        self.layout.browse_articles_button.configure(state=articles_state)
        self.layout.clear_articles_button.configure(state=articles_state)

        self.layout.run_panel.set_enabled(has_project and not running)
        self.layout.run_panel.set_running(running)

        # Queue(0) and Logs(2) always enabled. Outputs(1), Diagnostics(3), Profile(4) depend on project.
        state = "normal" if has_project else "disabled"
        for tab_index in (1, 3, 4):
            try:
                self.layout.right_notebook.tab(tab_index, state=state)
            except tk.TclError:
                pass
