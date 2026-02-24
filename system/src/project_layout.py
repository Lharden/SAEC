"""Filesystem layout helpers for dedicated project outputs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


REQUIRED_RELATIVE_DIRS: tuple[str, ...] = (
    "inputs",
    "inputs/articles",
    "outputs",
    "outputs/work",
    "outputs/yamls",
    "outputs/consolidated",
    "logs",
    "config",
    "config/profiles",
)


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved paths for one project root."""

    root: Path
    inputs_dir: Path
    articles_dir: Path
    outputs_dir: Path
    outputs_work: Path
    outputs_yamls: Path
    outputs_consolidated: Path
    logs_dir: Path
    config_dir: Path
    profiles_dir: Path
    project_env: Path
    profile_active_json: Path
    mapping_csv: Path
    project_json: Path


def collect_project_paths(project_root: Path) -> ProjectPaths:
    root = project_root.resolve()
    inputs_dir = root / "inputs"
    outputs_dir = root / "outputs"
    config_dir = root / "config"
    return ProjectPaths(
        root=root,
        inputs_dir=inputs_dir,
        articles_dir=inputs_dir / "articles",
        outputs_dir=outputs_dir,
        outputs_work=outputs_dir / "work",
        outputs_yamls=outputs_dir / "yamls",
        outputs_consolidated=outputs_dir / "consolidated",
        logs_dir=root / "logs",
        config_dir=config_dir,
        profiles_dir=config_dir / "profiles",
        project_env=config_dir / "project.env",
        profile_active_json=config_dir / "profile_active.json",
        mapping_csv=root / "mapping.csv",
        project_json=root / "project.json",
    )


def missing_required_paths(project_root: Path) -> list[Path]:
    root = project_root.resolve()
    missing: list[Path] = []
    for rel in REQUIRED_RELATIVE_DIRS:
        target = root / rel
        if not target.exists() or not target.is_dir():
            missing.append(target)
    return missing


def ensure_project_layout(project_root: Path) -> ProjectPaths:
    paths = collect_project_paths(project_root)
    for rel in REQUIRED_RELATIVE_DIRS:
        (paths.root / rel).mkdir(parents=True, exist_ok=True)

    if not paths.project_env.exists():
        paths.project_env.write_text(
            "# Project scoped overrides\n"
            "# SAEC_ARTICLES_PATH=\n"
            "# SAEC_EXTRACTION_PATH=\n",
            encoding="utf-8",
        )

    if not paths.mapping_csv.exists():
        with open(paths.mapping_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"],
            )
            writer.writeheader()

    return paths
