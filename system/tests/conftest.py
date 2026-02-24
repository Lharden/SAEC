"""Shared test fixtures for SAEC test suite."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ── Shared Dummy Classes ─────────────────────────────────────────


class DummyPaths:
    """Minimal Paths stand-in rooted at a tmp_path."""

    def __init__(self, root: Path) -> None:
        self.PROJECT_ROOT = root
        self.SYSTEM = root / "system"
        self.ARTICLES = root / "articles"
        self.EXTRACTION = root / "Extraction"
        self.OUTPUTS = self.EXTRACTION / "outputs"
        self.WORK = self.OUTPUTS / "work"
        self.YAMLS = self.OUTPUTS / "yamls"
        self.CONSOLIDATED = self.OUTPUTS / "consolidated"
        self.MAPPING_CSV = self.EXTRACTION / "mapping.csv"
        self.GUIA_PROMPT = root / "guia.md"

    def ensure_dirs(self) -> None:
        for d in [self.WORK, self.YAMLS, self.CONSOLIDATED]:
            d.mkdir(parents=True, exist_ok=True)

    def get_article_work_dir(self, artigo_id: str) -> Path:
        d = self.WORK / artigo_id
        d.mkdir(parents=True, exist_ok=True)
        return d


class DummyExtractionConfig:
    """Minimal ExtractionConfig stand-in."""

    IMAGE_DPI = 150
    FORCE_HYBRID = True


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def dummy_paths(tmp_path: Path) -> DummyPaths:
    """Create a DummyPaths rooted at a temporary directory with standard dirs."""
    paths = DummyPaths(tmp_path)
    paths.ensure_dirs()
    return paths


@pytest.fixture()
def dummy_extraction_config() -> DummyExtractionConfig:
    return DummyExtractionConfig()


# ── Helper Functions (importable) ────────────────────────────────


def write_test_mapping(
    mapping_path: Path,
    artigo_id: str,
    filename: str,
) -> None:
    """Write a single-row mapping.csv for tests."""
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "ArtigoID": artigo_id,
                "Arquivo": filename,
                "Processado": "Não",
                "Status": "",
            }
        )

