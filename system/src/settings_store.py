"""Persistent UI settings storage for workspace-aware desktop UX."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "recent_workspaces": [],
    "last_workspace": "",
    "last_project_by_workspace": {},
    "articles_override_by_project": {},
    "selected_preset": "pilot",
    "window_geometry": "",  # "WIDTHxHEIGHT+X+Y" format
    "active_tab": 0,        # Index of the active right-panel tab
    "main_sash_position": 320,
    "notify_on_completion": True,
    "setup_completed": False,
}


class SettingsStore:
    """Simple JSON-backed key/value store for UI session state."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()
        self.file_path = self.base_dir / "ui_settings.json"

    def _ensure_base_dir(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _normalize(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = dict(DEFAULT_SETTINGS)
        if not payload:
            return data
        for key in DEFAULT_SETTINGS:
            if key in payload:
                data[key] = payload[key]
        if not isinstance(data["recent_workspaces"], list):
            data["recent_workspaces"] = []
        if not isinstance(data["last_project_by_workspace"], dict):
            data["last_project_by_workspace"] = {}
        if not isinstance(data.get("articles_override_by_project"), dict):
            data["articles_override_by_project"] = {}
        if not isinstance(data["last_workspace"], str):
            data["last_workspace"] = ""
        if not isinstance(data["selected_preset"], str) or not data["selected_preset"]:
            data["selected_preset"] = "pilot"
        if not isinstance(data.get("window_geometry"), str):
            data["window_geometry"] = ""
        if not isinstance(data.get("active_tab"), int):
            data["active_tab"] = 0
        if not isinstance(data.get("main_sash_position"), int):
            data["main_sash_position"] = 320
        if not isinstance(data.get("notify_on_completion"), bool):
            data["notify_on_completion"] = True
        if not isinstance(data.get("setup_completed"), bool):
            data["setup_completed"] = False
        return data

    def load(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return dict(DEFAULT_SETTINGS)
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        except Exception:
            return dict(DEFAULT_SETTINGS)
        if not isinstance(payload, dict):
            return dict(DEFAULT_SETTINGS)
        return self._normalize(payload)

    def save(self, data: dict[str, Any]) -> None:
        self._ensure_base_dir()
        normalized = self._normalize(data)
        self.file_path.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_recent_workspace(
        self, workspace_root: Path, *, max_items: int = 10
    ) -> dict[str, Any]:
        data = self.load()
        normalized = str(workspace_root.resolve())
        existing = [item for item in data["recent_workspaces"] if item != normalized]
        data["recent_workspaces"] = [normalized] + existing[: max_items - 1]
        data["last_workspace"] = normalized
        self.save(data)
        return data

    def save_window_state(
        self,
        *,
        geometry: str,
        active_tab: int,
        main_sash_position: int | None = None,
    ) -> None:
        data = self.load()
        data["window_geometry"] = geometry
        data["active_tab"] = active_tab
        if main_sash_position is not None:
            data["main_sash_position"] = main_sash_position
        self.save(data)

    def get_window_state(self) -> dict[str, Any]:
        data = self.load()
        return {
            "geometry": data.get("window_geometry", ""),
            "active_tab": data.get("active_tab", 0),
            "main_sash_position": data.get("main_sash_position", 320),
        }

    def set_last_project(self, workspace_root: Path, project_id: str) -> dict[str, Any]:
        data = self.load()
        workspace_key = str(workspace_root.resolve())
        by_workspace = dict(data["last_project_by_workspace"])
        by_workspace[workspace_key] = project_id
        data["last_project_by_workspace"] = by_workspace
        data["last_workspace"] = workspace_key
        self.save(data)
        return data

    def get_articles_override(self, project_key: str) -> str:
        data = self.load()
        overrides = data.get("articles_override_by_project", {})
        return str(overrides.get(project_key, ""))

    def set_articles_override(self, project_key: str, path: str) -> None:
        data = self.load()
        overrides = dict(data.get("articles_override_by_project", {}))
        if path:
            overrides[project_key] = path
        else:
            overrides.pop(project_key, None)
        data["articles_override_by_project"] = overrides
        self.save(data)
