"""Project and workspace management for the SAEC GUI."""

from __future__ import annotations

import logging
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

from gui.dialog_profile import prompt_project_profile_setup
from gui.dialog_project import prompt_new_project
from gui.dialog_setup import prompt_first_run_setup
from gui.dialog_startup import prompt_startup_choice
from gui.dialog_workspace import choose_workspace
from gui.project_config import ProjectConfig, get_blank_project_defaults
from profile_engine.project_profiles import get_active_profile_ref
from run_queue import RunQueue
from workspace import create_project, ensure_workspace, list_projects

if TYPE_CHECKING:
    from gui.app import SAECWin98App


class ProjectManager:
    """Handles workspace/project CRUD, env file I/O, and articles folder override."""

    def __init__(self, app: SAECWin98App) -> None:
        self._app = app
        self._logger = logging.getLogger("saec.gui.project")

    # ------------------------------------------------------------------
    # Env file I/O
    # ------------------------------------------------------------------

    def read_env_values(self) -> dict[str, str]:
        app = self._app
        values: dict[str, str] = {}
        if not app._env_path.exists():
            return values
        for raw in app._env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def write_env_file(self, values: dict[str, str]) -> None:
        app = self._app
        self.write_env_to_path(app._env_path, values)

        if app.project_root:
            project_config = ProjectConfig(app.project_root)
            project_config.save(values)
            app.layout.status_var.set("Configuracoes salvas no projeto")

    @staticmethod
    def write_env_to_path(env_path: Path, values: dict[str, str]) -> None:
        updates = {key: ("" if value is None else str(value)) for key, value in values.items()}
        existing_text = ""
        trailing_newline = True
        lines: list[str]

        if env_path.exists():
            existing_text = env_path.read_text(encoding="utf-8", errors="replace")
            lines = existing_text.splitlines()
            trailing_newline = existing_text.endswith(("\n", "\r"))
            if not lines:
                lines = ["# SAEC runtime configuration"]
        else:
            lines = ["# SAEC runtime configuration"]

        existing_keys: set[str] = set()
        rendered_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                rendered_lines.append(line)
                continue

            key, _current_value = line.split("=", 1)
            clean_key = key.strip()
            existing_keys.add(clean_key)
            if clean_key in updates:
                rendered_lines.append(f"{clean_key}={updates[clean_key]}")
            else:
                rendered_lines.append(line)

        appended: list[tuple[str, str]] = []
        for key, value in updates.items():
            if key not in existing_keys:
                appended.append((key, value))

        if "OLLAMA_ENABLED" not in existing_keys and not any(
            key == "OLLAMA_ENABLED" for key, _ in appended
        ):
            appended.append(("OLLAMA_ENABLED", "true"))

        for key, value in appended:
            rendered_lines.append(f"{key}={value}")

        output = "\n".join(rendered_lines)
        if trailing_newline:
            output += "\n"

        env_path.write_text(output, encoding="utf-8")

    def open_setup_dialog(self) -> None:
        app = self._app
        env_values = self.read_env_values()
        config = prompt_first_run_setup(
            app,
            default_ollama_url=env_values.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            existing_values=env_values,
        )
        if not config:
            return
        self.write_env_file(config)
        results = app._run_diagnostics_checks()
        app._warn_if_no_provider_ready(results)

    # ------------------------------------------------------------------
    # Workspace selection
    # ------------------------------------------------------------------

    def on_browse_workspace(self) -> None:
        app = self._app
        initial = app.workspace_root or Path.home()
        selected = choose_workspace(app, initial_dir=initial)
        if selected is None:
            return
        self.set_workspace(selected)

    def on_workspace_selected(self, _event=None) -> None:
        value = self._app.layout.workspace_combo.get().strip()
        if not value:
            return
        self.set_workspace(Path(value))

    def set_workspace(self, workspace_root: Path) -> None:
        app = self._app
        if (
            app.workspace_root is not None
            and workspace_root.resolve() != app.workspace_root.resolve()
        ):
            app._save_queue_history()

        cfg = ensure_workspace(workspace_root)
        app.workspace_root = cfg.root
        app._queue_history_path = cfg.meta_dir / "queue_history.json"

        settings = app._settings_store.add_recent_workspace(cfg.root)
        recent = settings.get("recent_workspaces", [])
        app.layout.workspace_combo.configure(values=recent)
        app.layout.workspace_combo.set(str(cfg.root))

        app._queue = RunQueue()
        app._load_queue_history()

        app.layout.status_panel.set_workspace(cfg.root)
        app.layout.status_var.set(f"Workspace selected: {cfg.root}")

        app._configure_logging(cfg.meta_dir / "logs")
        self.refresh_projects()
        app._run_diagnostics_checks()
        app._refresh_queue_ui()
        app._refresh_enabled_states()

    # ------------------------------------------------------------------
    # Project selection
    # ------------------------------------------------------------------

    def refresh_projects(self) -> None:
        app = self._app
        if app.workspace_root is None:
            app.layout.project_combo.configure(values=[])
            app.layout.project_combo.set("")
            app._project_name_to_id = {}
            app.project_root = None
            app.layout.outputs_panel.set_project_root(None)
            app.layout.profile_panel.set_project_root(None)
            app.layout.status_panel.set_project(None)
            app._refresh_enabled_states()
            return

        projects = list_projects(app.workspace_root)
        labels: list[str] = []
        app._project_name_to_id = {}
        for project in projects:
            label = f"{project.project_id} | {project.name}"
            labels.append(label)
            app._project_name_to_id[label] = project.project_id

        app.layout.project_combo.configure(values=labels)

        if labels:
            settings = app._settings_store.load()
            key = str(app.workspace_root)
            last = settings.get("last_project_by_workspace", {}).get(key, "")
            selected = next(
                (label for label in labels if label.startswith(f"{last} |")), labels[0]
            )
            app.layout.project_combo.set(selected)
            self.select_project_from_label(selected)
        else:
            app.layout.project_combo.set("")
            app.project_root = None
            app.layout.outputs_panel.set_project_root(None)
            app.layout.profile_panel.set_project_root(None)
            app.layout.status_panel.set_project(None)

        app._refresh_enabled_states()

    def on_project_selected(self, _event=None) -> None:
        label = self._app.layout.project_combo.get().strip()
        if not label:
            return
        self.select_project_from_label(label)

    def select_project_from_label(self, label: str) -> None:
        app = self._app
        if app.workspace_root is None:
            return

        project_id = app._project_name_to_id.get(label)
        if project_id is None:
            project_id = label.split(" | ", 1)[0] if " | " in label else label

        root = app.workspace_root / "projects" / project_id
        app.project_root = root.resolve()

        self._load_project_config()
        self._ensure_project_profile_configured(interactive=True)

        self.restore_articles_override()
        app.layout.outputs_panel.set_project_root(app.project_root)
        app.layout.profile_panel.set_project_root(app.project_root)
        app.layout.status_panel.set_project(
            app.project_root, articles_dir=self.effective_articles_dir()
        )
        app.layout.status_var.set(f"Project selected: {project_id}")
        app._settings_store.set_last_project(app.workspace_root, project_id)

        app._configure_logging(app.project_root / "logs")
        app._run_diagnostics_checks()
        app._refresh_enabled_states()

    def select_project_by_id(self, project_id: str) -> None:
        app = self._app
        if not app.workspace_root:
            return

        projects = list_projects(app.workspace_root)
        for project in projects:
            if project.project_id == project_id:
                label = f"{project.project_id} | {project.name}"
                app.layout.project_combo.set(label)
                self.select_project_from_label(label)
                break

    def on_new_project(self) -> None:
        app = self._app
        if app.workspace_root is None:
            messagebox.showwarning(
                "Workspace required", "Select a workspace first.", parent=app
            )
            return

        name = prompt_new_project(app)
        if not name:
            return

        self.create_new_project_with_config(name)

    def create_new_project_with_config(self, name: str) -> None:
        app = self._app
        if not app.workspace_root:
            return

        try:
            project = create_project(app.workspace_root, name=name)
        except FileExistsError:
            messagebox.showerror(
                "Project exists",
                "A project with this id already exists.",
                parent=app,
            )
            return

        self.refresh_projects()
        label = f"{project.project_id} | {project.name}"
        app.layout.project_combo.set(label)
        self.select_project_from_label(label)

        if app.project_root:
            config = ProjectConfig(app.project_root)
            blank_defaults = get_blank_project_defaults()
            config.save(blank_defaults)
            self.write_env_file(blank_defaults)
            app.layout.status_var.set(
                "Novo projeto criado. Defina o perfil metodológico do projeto."
            )
            app.after(500, self.open_setup_dialog)

    def _load_project_config(self) -> None:
        app = self._app
        if not app.project_root:
            return

        config = ProjectConfig(app.project_root)
        if config.exists():
            values = config.load()
            self.write_env_file(values)
            app.layout.status_var.set("Configuracoes do projeto carregadas")

    def _ensure_project_profile_configured(self, *, interactive: bool) -> bool:
        app = self._app
        if not app.project_root:
            return False

        active = get_active_profile_ref(app.project_root)
        if active is not None:
            app.layout.status_var.set(
                f"Perfil ativo: {active.profile_id} v{active.version}"
            )
            app.layout.profile_panel.refresh()
            return True

        if not interactive:
            return False

        messagebox.showinfo(
            "Profile required",
            (
                "This project has no active profile.\n\n"
                "Configure one now (preset, YAML, XLSX, or custom builder) "
                "to enable pipeline execution."
            ),
            parent=app,
        )
        ok = prompt_project_profile_setup(app, app.project_root)
        if not ok:
            app.layout.status_var.set(
                "Projeto sem perfil ativo. Configure o perfil para executar o pipeline."
            )
            return False

        active = get_active_profile_ref(app.project_root)
        if active is None:
            app.layout.status_var.set(
                "Falha ao ativar perfil. Verifique a configuracao do projeto."
            )
            return False
        app.layout.status_var.set(
            f"Perfil ativo: {active.profile_id} v{active.version}"
        )
        app.layout.profile_panel.refresh()
        return True

    def on_configure_profile(self) -> None:
        app = self._app
        if app.project_root is None:
            messagebox.showwarning(
                "Project required", "Select a project first.", parent=app
            )
            return
        ok = prompt_project_profile_setup(app, app.project_root)
        if ok:
            active = get_active_profile_ref(app.project_root)
            if active is not None:
                app.layout.status_var.set(
                    f"Perfil ativo: {active.profile_id} v{active.version}"
                )
            app.layout.profile_panel.refresh()

    # ------------------------------------------------------------------
    # Startup flow
    # ------------------------------------------------------------------

    def ensure_first_run_setup(self) -> None:
        app = self._app
        settings = app._settings_store.load()
        recent = settings.get("recent_workspaces", [])

        choice = prompt_startup_choice(app, recent)
        if choice is None:
            last_ws = settings.get("last_workspace", "")
            if last_ws and Path(last_ws).exists():
                self.set_workspace(Path(last_ws))
            return

        action, workspace = choice

        if action == "new":
            if workspace is None:
                workspace = choose_workspace(app, initial_dir=Path.home())
                if workspace is None:
                    return

            self.set_workspace(workspace)

            if app.workspace_root:
                name = prompt_new_project(app)
                if name:
                    self.create_new_project_with_config(name)
        else:
            if workspace is None and recent:
                workspace = Path(recent[0])

            if workspace and workspace.exists():
                self.set_workspace(workspace)
                ws_key = str(workspace)
                last_project = settings.get("last_project_by_workspace", {}).get(
                    ws_key, ""
                )
                if last_project:
                    self.select_project_by_id(last_project)

    # ------------------------------------------------------------------
    # Articles directory override
    # ------------------------------------------------------------------

    def effective_articles_dir(self) -> Path | None:
        app = self._app
        if app._articles_override is not None:
            return app._articles_override
        if app.project_root is not None:
            return app.project_root / "inputs" / "articles"
        return None

    def _project_key(self) -> str:
        app = self._app
        return str(app.project_root.resolve()) if app.project_root else ""

    def update_articles_display(self) -> None:
        app = self._app
        if app._articles_override is not None:
            app.layout.articles_path_var.set(str(app._articles_override))
        elif app.project_root is not None:
            app.layout.articles_path_var.set("inputs/articles/ (default)")
        else:
            app.layout.articles_path_var.set("(default)")

    def on_browse_articles(self) -> None:
        app = self._app
        initial = app._articles_override or (
            app.project_root / "inputs" / "articles" if app.project_root else Path.home()
        )
        selected = filedialog.askdirectory(
            parent=app,
            title="Select articles folder (with PDFs)",
            initialdir=str(initial),
        )
        if not selected:
            return

        folder = Path(selected)
        pdfs = list(folder.glob("*.pdf"))
        if not pdfs:
            messagebox.showwarning(
                "No PDFs found",
                f"No .pdf files found in:\n{folder}\n\nSelect a folder containing PDF articles.",
                parent=app,
            )
            return

        app._articles_override = folder
        self.update_articles_display()
        app.layout.status_var.set(f"Articles folder: {folder} ({len(pdfs)} PDFs)")

        key = self._project_key()
        if key:
            app._settings_store.set_articles_override(key, str(folder))

        app.layout.status_panel.set_articles_source(str(folder), external=True)

    def on_clear_articles(self) -> None:
        app = self._app
        app._articles_override = None
        self.update_articles_display()
        app.layout.status_var.set("Articles folder reverted to project default.")

        key = self._project_key()
        if key:
            app._settings_store.set_articles_override(key, "")

        app.layout.status_panel.set_articles_source(None, external=False)

    def restore_articles_override(self) -> None:
        app = self._app
        key = self._project_key()
        if not key:
            app._articles_override = None
            self.update_articles_display()
            return

        saved = app._settings_store.get_articles_override(key)
        if saved and Path(saved).exists():
            app._articles_override = Path(saved)
        else:
            app._articles_override = None
        self.update_articles_display()
