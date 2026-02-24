"""Safety guardrail rules for GUI-triggered pipeline runs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from job_runner import RunRequest
from profile_engine.project_profiles import require_project_profile


Severity = Literal["warning", "danger"]


@dataclass(frozen=True)
class SafetyConfirmation:
    """A confirmation prompt that must be accepted before queueing."""

    key: str
    title: str
    message: str
    severity: Severity = "warning"


@dataclass(frozen=True)
class SafetyEvaluation:
    """Outcome of policy evaluation for a RunRequest."""

    blocking_errors: list[str]
    confirmations: list[SafetyConfirmation]


def _pdf_count(project_root: Path, articles_dir: Path | None = None) -> int:
    target = articles_dir or (project_root / "inputs" / "articles")
    if not target.exists():
        return 0
    return sum(1 for _ in target.glob("*.pdf"))


def _pdf_names(project_root: Path, articles_dir: Path | None = None) -> set[str]:
    target = articles_dir or (project_root / "inputs" / "articles")
    if not target.exists():
        return set()
    return {path.name for path in target.glob("*.pdf")}


def _read_mapping_rows(project_root: Path) -> list[dict[str, str]] | None:
    mapping_path = project_root / "mapping.csv"
    if not mapping_path.exists():
        return None
    try:
        with open(mapping_path, "r", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
    except (OSError, csv.Error):
        return []

    valid_rows: list[dict[str, str]] = []
    for row in rows:
        arquivo = (row.get("Arquivo", "") or "").strip()
        artigo_id = (row.get("ArtigoID", "") or "").strip()
        if not arquivo or not artigo_id:
            continue
        valid_rows.append({"Arquivo": arquivo, "ArtigoID": artigo_id})
    return valid_rows


def has_ingest_outputs(project_root: Path, *, article_id: str = "") -> bool:
    """Return True if step-2 outputs exist for the requested scope."""
    work_dir = project_root / "outputs" / "work"
    if not work_dir.exists():
        return False

    normalized = article_id.strip()
    if normalized:
        return (work_dir / normalized / "hybrid.json").exists()

    return any(p.is_file() for p in work_dir.glob("*/hybrid.json"))


def evaluate_safety(
    request: RunRequest,
    *,
    project_root: Path | None,
    articles_dir: Path | None = None,
) -> SafetyEvaluation:
    """Evaluate guardrails and return blocking errors + required confirmations."""
    errors: list[str] = []
    confirmations: list[SafetyConfirmation] = []

    if project_root is None:
        errors.append("Project root is not set.")
        return SafetyEvaluation(blocking_errors=errors, confirmations=confirmations)

    if not project_root.exists():
        errors.append(f"Project path does not exist: {project_root}")
        return SafetyEvaluation(blocking_errors=errors, confirmations=confirmations)

    profile_ok, profile_error = require_project_profile(project_root)
    if not profile_ok:
        errors.append(profile_error)

    pdfs = _pdf_count(project_root, articles_dir)
    if pdfs < 1:
        errors.append(
            "No PDF files found in inputs/articles/. Add at least one PDF before running."
        )

    requires_mapping = request.mode == "all" or (
        request.mode == "step" and request.step in (2, 3, 5)
    )
    if requires_mapping and pdfs > 0:
        mapping_rows = _read_mapping_rows(project_root)
        if mapping_rows is None:
            errors.append("Mapping file not found (mapping.csv). Run Step 1 first.")
        elif len(mapping_rows) < 1:
            errors.append("Mapping file is empty. Run Step 1 to regenerate mapping.csv.")
        else:
            mapped_files = {row["Arquivo"] for row in mapping_rows}
            if not _pdf_names(project_root, articles_dir).issubset(mapped_files):
                errors.append(
                    "Mapping is out of date with inputs/articles. Run Step 1 to sync mapping.csv."
                )

    if request.mode == "step" and request.step == 3:
        if not has_ingest_outputs(project_root, article_id=request.article_id):
            errors.append(
                "Step 3 requires ingest outputs (hybrid.json). Run Step 2 first."
            )

    if request.force:
        if request.mode == "all":
            confirmations.append(
                SafetyConfirmation(
                    key="force",
                    title="Force Reprocessing",
                    message=(
                        "Force mode is enabled. Existing outputs may be overwritten."
                    ),
                    severity="warning",
                )
            )
            confirmations.append(
                SafetyConfirmation(
                    key="force_all",
                    title="Confirm Full Reprocessing",
                    message=(
                        "This will reprocess ALL articles and may overwrite previous results. "
                        "Do you want to continue?"
                    ),
                    severity="danger",
                )
            )
        else:
            confirmations.append(
                SafetyConfirmation(
                    key="force",
                    title="Force Reprocessing",
                    message=(
                        "Force mode is enabled for this run. Existing outputs may be overwritten."
                    ),
                    severity="warning",
                )
            )

    return SafetyEvaluation(blocking_errors=errors, confirmations=confirmations)
