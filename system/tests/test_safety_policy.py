from __future__ import annotations

from pathlib import Path

from job_runner import RunRequest
from safety_policy import evaluate_safety, has_ingest_outputs


def _request(*, mode: str = "step", step: int | None = 2, force: bool = False, article: str = "") -> RunRequest:
    return RunRequest(
        mode="all" if mode == "all" else "step",
        step=step,
        article_id=article,
        dry_run=False,
        force=force,
        log_level="INFO",
    )


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "inputs" / "articles").mkdir(parents=True)
    (project / "outputs" / "work").mkdir(parents=True)
    return project


def _write_mapping(project: Path, rows: list[tuple[str, str]]) -> None:
    mapping = project / "mapping.csv"
    lines = ["ArtigoID,Arquivo,Processado,Status"]
    for artigo_id, arquivo in rows:
        lines.append(f"{artigo_id},{arquivo},Não,")
    mapping.write_text("\n".join(lines), encoding="utf-8")


def test_blocks_when_no_pdfs_present(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    result = evaluate_safety(_request(step=2), project_root=project)

    assert any("No PDF files" in msg for msg in result.blocking_errors)


def test_force_all_requires_double_confirmation(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "inputs" / "articles" / "a.pdf").write_bytes(b"x")

    result = evaluate_safety(_request(mode="all", step=None, force=True), project_root=project)

    assert len(result.confirmations) == 2
    assert [item.key for item in result.confirmations] == ["force", "force_all"]


def test_step_three_requires_ingest_outputs(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "inputs" / "articles" / "a.pdf").write_bytes(b"x")

    result = evaluate_safety(_request(step=3), project_root=project)

    assert any("Step 3 requires ingest outputs" in msg for msg in result.blocking_errors)


def test_ingest_outputs_detected_for_specific_article(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "outputs" / "work" / "ART_001").mkdir(parents=True)
    (project / "outputs" / "work" / "ART_001" / "hybrid.json").write_text("{}", encoding="utf-8")

    assert has_ingest_outputs(project, article_id="ART_001") is True


def test_step_three_allowed_when_ingest_outputs_exist(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "inputs" / "articles" / "a.pdf").write_bytes(b"x")
    (project / "outputs" / "work" / "ART_001").mkdir(parents=True)
    (project / "outputs" / "work" / "ART_001" / "hybrid.json").write_text("{}", encoding="utf-8")
    _write_mapping(project, [("ART_001", "a.pdf")])

    result = evaluate_safety(_request(step=3, article="ART_001"), project_root=project)

    assert result.blocking_errors == []


def test_step_two_blocks_when_mapping_missing(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "inputs" / "articles" / "a.pdf").write_bytes(b"x")

    result = evaluate_safety(_request(step=2), project_root=project)

    assert any("Mapping file not found" in msg for msg in result.blocking_errors)


def test_step_two_blocks_when_mapping_empty(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "inputs" / "articles" / "a.pdf").write_bytes(b"x")
    _write_mapping(project, [])

    result = evaluate_safety(_request(step=2), project_root=project)

    assert any("Mapping file is empty" in msg for msg in result.blocking_errors)


def test_step_two_blocks_when_mapping_out_of_date(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    (project / "inputs" / "articles" / "a.pdf").write_bytes(b"x")
    (project / "inputs" / "articles" / "b.pdf").write_bytes(b"y")
    _write_mapping(project, [("ART_001", "a.pdf")])

    result = evaluate_safety(_request(step=2), project_root=project)

    assert any("Mapping is out of date" in msg for msg in result.blocking_errors)
