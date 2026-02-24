from __future__ import annotations

import json
from pathlib import Path

from job_runner import RunRequest
from profile_engine.project_profiles import bootstrap_profile
from safety_policy import evaluate_safety


def _request() -> RunRequest:
    return RunRequest(
        mode="step",
        step=2,
        article_id="",
        dry_run=False,
        force=False,
        log_level="INFO",
    )


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "inputs" / "articles").mkdir(parents=True, exist_ok=True)
    (root / "outputs" / "work").mkdir(parents=True, exist_ok=True)
    (root / "inputs" / "articles" / "a.pdf").write_bytes(b"x")
    (root / "mapping.csv").write_text(
        "ArtigoID,Arquivo,Processado,Status\nART_001,a.pdf,Não,\n",
        encoding="utf-8",
    )
    (root / "project.json").write_text(
        json.dumps(
            {
                "project_id": "p1",
                "name": "p1",
                "created_at": "2026-02-19T00:00:00+00:00",
                "profile_required": True,
            }
        ),
        encoding="utf-8",
    )
    (root / "config" / "profiles").mkdir(parents=True, exist_ok=True)
    return root


def test_blocks_run_when_project_profile_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    result = evaluate_safety(_request(), project_root=project)

    assert any("Project profile is not configured" in msg for msg in result.blocking_errors)


def test_allows_run_after_profile_bootstrap(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    bootstrap_profile(project, profile_id="cimo_v3_3", activate=True)

    result = evaluate_safety(_request(), project_root=project)

    assert not any("Project profile is not configured" in msg for msg in result.blocking_errors)


