"""Win98-style desktop shell for SAEC-O&G."""

from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox

from gui.dialog_project import prompt_new_project
from gui.dialog_workspace import choose_workspace
from gui.layout_main import MainLayout, build_main_layout
from gui.win98_theme import apply_win98_theme
from job_runner import PipelineJobRunner, RunResult, resolve_cli_runner
from run_queue import RunQueue
from settings_store import SettingsStore
from workspace import create_project, ensure_workspace, list_projects


class SAECWin98App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("SAEC-O&G - Win98 Edition")
        self.geometry("1180x760")
        self.minsize(1000, 640)

        apply_win98_theme(self)

        self.workspace_root: Path | None = None
        self.project_root: Path | None = None
        self._project_name_to_id: dict[str, str] = {}

        self._settings_store = SettingsStore(Path.home() / ".saec-og")
        self._queue = RunQueue()

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

        self.layout: MainLayout = build_main_layout(
            self, on_run=self._on_run, on_cancel=self._on_cancel
        )
        self._wire_events()
        self._build_menu()
        self._restore_session()
        self._refresh_queue_ui()

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
        self.layout.workspace_combo.bind(
            "<<ComboboxSelected>>", self._on_workspace_selected
        )
        self.layout.project_combo.bind(
            "<<ComboboxSelected>>", self._on_project_selected
        )
        self.layout.new_project_button.configure(command=self._on_new_project)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=file_menu)

        workspace_menu = tk.Menu(menu, tearoff=False)
        workspace_menu.add_command(
            label="Select Workspace...", command=self._on_browse_workspace
        )
        menu.add_cascade(label="Workspace", menu=workspace_menu)

        project_menu = tk.Menu(menu, tearoff=False)
        project_menu.add_command(label="New Project...", command=self._on_new_project)
        menu.add_cascade(label="Project", menu=project_menu)

        pipeline_menu = tk.Menu(menu, tearoff=False)
        pipeline_menu.add_command(label="Run", command=self._on_run)
        pipeline_menu.add_command(label="Cancel", command=self._on_cancel)
        menu.add_cascade(label="Pipeline", menu=pipeline_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menu)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "SAEC-O&G Win98 Edition\n"
            "Workspace-aware desktop shell for CIMO extraction.",
            parent=self,
        )

    def _restore_session(self) -> None:
        settings = self._settings_store.load()
        recent = settings.get("recent_workspaces", [])
        self.layout.workspace_combo.configure(values=recent)

        last_workspace = settings.get("last_workspace", "")
        if not last_workspace:
            return

        workspace_path = Path(last_workspace)
        if workspace_path.exists():
            self._set_workspace(workspace_path)
        self._refresh_queue_ui()

    def _on_browse_workspace(self) -> None:
        initial = self.workspace_root or Path.home()
        selected = choose_workspace(self, initial_dir=initial)
        if selected is None:
            return
        self._set_workspace(selected)

    def _on_workspace_selected(self, _event=None) -> None:
        value = self.layout.workspace_combo.get().strip()
        if not value:
            return
        self._set_workspace(Path(value))

    def _set_workspace(self, workspace_root: Path) -> None:
        cfg = ensure_workspace(workspace_root)
        self.workspace_root = cfg.root

        settings = self._settings_store.add_recent_workspace(cfg.root)
        recent = settings.get("recent_workspaces", [])
        self.layout.workspace_combo.configure(values=recent)
        self.layout.workspace_combo.set(str(cfg.root))

        self.layout.status_panel.set_workspace(cfg.root)
        self.layout.status_var.set(f"Workspace selected: {cfg.root}")
        self._refresh_projects()

    def _refresh_projects(self) -> None:
        if self.workspace_root is None:
            self.layout.project_combo.configure(values=[])
            self.layout.project_combo.set("")
            self._project_name_to_id = {}
            return

        projects = list_projects(self.workspace_root)
        labels: list[str] = []
        self._project_name_to_id = {}
        for project in projects:
            label = f"{project.project_id} | {project.name}"
            labels.append(label)
            self._project_name_to_id[label] = project.project_id

        self.layout.project_combo.configure(values=labels)

        if labels:
            settings = self._settings_store.load()
            key = str(self.workspace_root)
            last = settings.get("last_project_by_workspace", {}).get(key, "")
            selected = next(
                (label for label in labels if label.startswith(f"{last} |")), labels[0]
            )
            self.layout.project_combo.set(selected)
            self._select_project_from_label(selected)
        else:
            self.layout.project_combo.set("")
            self.project_root = None
            self.layout.outputs_panel.set_project_root(None)
            self.layout.status_panel.set_project(None)

    def _on_project_selected(self, _event=None) -> None:
        label = self.layout.project_combo.get().strip()
        if not label:
            return
        self._select_project_from_label(label)

    def _select_project_from_label(self, label: str) -> None:
        if self.workspace_root is None:
            return

        project_id = self._project_name_to_id.get(label)
        if project_id is None:
            if " | " in label:
                project_id = label.split(" | ", 1)[0]
            else:
                project_id = label

        root = self.workspace_root / "projects" / project_id
        self.project_root = root.resolve()
        self.layout.outputs_panel.set_project_root(self.project_root)
        self.layout.status_panel.set_project(self.project_root)
        self.layout.status_var.set(f"Project selected: {project_id}")
        self._settings_store.set_last_project(self.workspace_root, project_id)

    def _on_new_project(self) -> None:
        if self.workspace_root is None:
            messagebox.showwarning(
                "Workspace required", "Select a workspace first.", parent=self
            )
            return

        name = prompt_new_project(self)
        if not name:
            return

        try:
            project = create_project(self.workspace_root, name=name)
        except FileExistsError:
            messagebox.showerror(
                "Project exists", "A project with this id already exists.", parent=self
            )
            return

        self._refresh_projects()
        label = f"{project.project_id} | {project.name}"
        self.layout.project_combo.set(label)
        self._select_project_from_label(label)

    def _on_run(self) -> None:
        if self.project_root is None:
            messagebox.showwarning(
                "Project required", "Select or create a project first.", parent=self
            )
            return

        if (
            self._runner.main_script is not None
            and not self._runner.main_script.exists()
        ):
            messagebox.showerror(
                "Runner error",
                f"Pipeline entrypoint not found: {self._runner.main_script}",
                parent=self,
            )
            return

        request = self.layout.run_panel.build_request(
            workspace_root=self.workspace_root,
            project_root=self.project_root,
        )

        item = self._queue.enqueue(request)
        self.layout.logs_panel.append_line(
            f"[queue] queued job={item.job_id} mode={item.request.mode} article={item.request.article_id or '-'}"
        )
        self._refresh_queue_ui()
        self._start_next_if_idle()

    def _on_cancel(self) -> None:
        self._runner.cancel()
        cancelled = self._queue.cancel_running()
        if cancelled is not None:
            self.layout.logs_panel.append_line(
                f"[queue] cancelled job={cancelled.job_id}"
            )
        self.layout.status_var.set("Cancelling...")
        self.layout.run_panel.set_running(False)
        self._refresh_queue_ui()
        self.after(10, self._start_next_if_idle)

    def _on_runner_output(self, line: str) -> None:
        self.after(0, lambda: self.layout.logs_panel.append_line(line))

    def _on_runner_complete(self, result: RunResult) -> None:
        def _done() -> None:
            finished = self._queue.finish_running(result)
            self.layout.logs_panel.append_line("--- run finished ---")
            if finished is not None:
                self.layout.logs_panel.append_line(
                    f"[queue] finished job={finished.job_id} status={finished.status} code={finished.return_code}"
                )
            if result.success:
                self.layout.status_var.set("Run completed successfully.")
            else:
                self.layout.status_var.set(f"Run failed (code={result.return_code}).")
            self.layout.outputs_panel.refresh()
            self.layout.status_panel.set_project(self.project_root)
            self.layout.run_panel.set_running(False)
            self._refresh_queue_ui()
            self._start_next_if_idle()

        self.after(0, _done)

    def _start_next_if_idle(self) -> None:
        if self._runner.is_running:
            return
        next_item = self._queue.start_next()
        if next_item is None:
            return

        self.layout.run_panel.set_running(True)
        self.layout.status_var.set(f"Running job {next_item.job_id}...")
        self.layout.logs_panel.append_line(
            f"[queue] starting job={next_item.job_id} mode={next_item.request.mode}"
        )
        self._refresh_queue_ui()

        self._runner.run_async(
            next_item.request,
            on_output=self._on_runner_output,
            on_complete=self._on_runner_complete,
        )

    def _refresh_queue_ui(self) -> None:
        items = self._queue.snapshot()
        self.layout.queue_panel.refresh(items)

        pending = sum(1 for item in items if item.status == "pending")
        running = sum(1 for item in items if item.status == "running")
        success = sum(1 for item in items if item.status == "success")
        failed = sum(1 for item in items if item.status == "failed")
        cancelled = sum(1 for item in items if item.status == "cancelled")
        self.layout.status_panel.update_queue_metrics(
            pending=pending,
            running=running,
            success=success,
            failed=failed,
            cancelled=cancelled,
        )
