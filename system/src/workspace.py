"""Workspace and project management for the desktop UI."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from project_layout import collect_project_paths, ensure_project_layout
from project_model import ProjectSummary


@dataclass(frozen=True)
class WorkspaceConfig:
    """Resolved workspace filesystem configuration."""

    root: Path
    meta_dir: Path
    projects_dir: Path
    settings_file: Path


def ensure_workspace(workspace_root: Path) -> WorkspaceConfig:
    root = workspace_root.resolve()
    meta_dir = root / ".saec"
    projects_dir = root / "projects"
    meta_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)
    settings_file = meta_dir / "ui_settings.json"
    return WorkspaceConfig(
        root=root,
        meta_dir=meta_dir,
        projects_dir=projects_dir,
        settings_file=settings_file,
    )


def sanitize_project_id(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return value or "project"


def _project_manifest_path(project_root: Path) -> Path:
    return collect_project_paths(project_root).project_json


def create_project(
    workspace_root: Path,
    *,
    name: str,
    project_id: str | None = None,
) -> ProjectSummary:
    cfg = ensure_workspace(workspace_root)
    normalized_id = sanitize_project_id(project_id or name)
    root = cfg.projects_dir / normalized_id
    manifest_path = _project_manifest_path(root)

    if manifest_path.exists():
        raise FileExistsError(f"Project already exists: {normalized_id}")

    ensure_project_layout(root)
    created_at = datetime.now(UTC).isoformat()
    summary = ProjectSummary(
        project_id=normalized_id,
        name=name.strip() or normalized_id,
        root=root.resolve(),
        created_at=created_at,
    )

    manifest_path.write_text(
        json.dumps(
            {
                **summary.to_dict(),
                "profile_required": True,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return summary


def list_projects(workspace_root: Path) -> list[ProjectSummary]:
    cfg = ensure_workspace(workspace_root)
    projects: list[ProjectSummary] = []

    for entry in sorted(cfg.projects_dir.iterdir(), key=lambda item: item.name.lower()):
        if not entry.is_dir():
            continue
        manifest_path = _project_manifest_path(entry)
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            projects.append(ProjectSummary.from_dict(data, root=entry.resolve()))
            continue

        projects.append(
            ProjectSummary(
                project_id=entry.name,
                name=entry.name,
                root=entry.resolve(),
                created_at="",
            )
        )

    return sorted(projects, key=lambda project: project.project_id.lower())
