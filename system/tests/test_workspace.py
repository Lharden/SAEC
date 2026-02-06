from __future__ import annotations

from pathlib import Path

import project_layout
import workspace


def test_ensure_workspace_creates_required_dirs(tmp_path: Path) -> None:
    cfg = workspace.ensure_workspace(tmp_path)

    assert cfg.root == tmp_path.resolve()
    assert cfg.meta_dir.exists()
    assert cfg.projects_dir.exists()
    assert cfg.settings_file.parent == cfg.meta_dir


def test_create_project_creates_layout_and_manifest(tmp_path: Path) -> None:
    workspace.ensure_workspace(tmp_path)

    project = workspace.create_project(tmp_path, name="Pilot Project")
    paths = project_layout.collect_project_paths(project.root)

    assert project.project_id == "pilot-project"
    assert project.name == "Pilot Project"
    assert paths.articles_dir.exists()
    assert paths.outputs_work.exists()
    assert paths.outputs_yamls.exists()
    assert paths.outputs_consolidated.exists()
    assert paths.logs_dir.exists()
    assert paths.project_json.exists()


def test_list_projects_returns_created_projects_sorted(tmp_path: Path) -> None:
    workspace.ensure_workspace(tmp_path)
    workspace.create_project(tmp_path, name="Beta")
    workspace.create_project(tmp_path, name="Alpha")

    projects = workspace.list_projects(tmp_path)

    assert [p.project_id for p in projects] == ["alpha", "beta"]
