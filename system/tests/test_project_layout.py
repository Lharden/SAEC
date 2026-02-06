from __future__ import annotations

from pathlib import Path

import project_layout


def test_missing_required_paths_detects_not_created_layout(tmp_path: Path) -> None:
    missing = project_layout.missing_required_paths(tmp_path)
    assert missing


def test_ensure_project_layout_creates_required_paths(tmp_path: Path) -> None:
    project_layout.ensure_project_layout(tmp_path)

    missing = project_layout.missing_required_paths(tmp_path)
    paths = project_layout.collect_project_paths(tmp_path)

    assert not missing
    assert paths.articles_dir.exists()
    assert paths.outputs_work.exists()
    assert paths.outputs_yamls.exists()
    assert paths.outputs_consolidated.exists()
    assert paths.logs_dir.exists()
    assert paths.config_dir.exists()
