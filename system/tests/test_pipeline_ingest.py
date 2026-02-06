from __future__ import annotations

import csv
from pathlib import Path

from pipeline_ingest import run_ingest


class DummyPaths:
    def __init__(self, root: Path) -> None:
        self.PROJECT_ROOT = root
        self.ARTICLES = root / "articles"
        self.EXTRACTION = root / "Extraction"
        self.OUTPUTS = self.EXTRACTION / "outputs"
        self.WORK = self.OUTPUTS / "work"
        self.YAMLS = self.OUTPUTS / "yamls"
        self.CONSOLIDATED = self.OUTPUTS / "consolidated"
        self.MAPPING_CSV = self.EXTRACTION / "mapping.csv"


class DummyExtractionConfig:
    IMAGE_DPI = 150


def _write_mapping(mapping_path: Path, artigo_id: str, filename: str) -> None:
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"])
        writer.writeheader()
        writer.writerow({"ArtigoID": artigo_id, "Arquivo": filename, "Processado": "Não", "Status": ""})


def test_run_ingest_with_mocked_pdf(monkeypatch, tmp_path: Path):
    paths = DummyPaths(tmp_path)
    paths.ARTICLES.mkdir(parents=True, exist_ok=True)
    pdf_path = paths.ARTICLES / "paper.pdf"
    pdf_path.write_text("dummy", encoding="utf-8")

    _write_mapping(paths.MAPPING_CSV, "ART_001", "paper.pdf")

    def fake_get_pdf_info(_):
        return {"num_pages": 1, "file_size_mb": 0.1}

    def fake_check_pdf_quality(_):
        return {}

    def fake_analyze_pdf_pages(_):
        return [{"page_num": 1, "strategy": "text"}]

    def fake_extract_hybrid(_, __, dpi=150):
        return {
            "pages": [{"page_num": 1, "type": "text", "content": "text"}],
            "analysis": [],
            "stats": {"text_pages": 1, "image_pages": 0, "skipped_pages": 0},
        }

    import pipeline_ingest as mod

    monkeypatch.setattr(mod, "get_pdf_info", fake_get_pdf_info)
    monkeypatch.setattr(mod, "check_pdf_quality", fake_check_pdf_quality)
    monkeypatch.setattr(mod, "analyze_pdf_pages", fake_analyze_pdf_pages)
    monkeypatch.setattr(mod, "extract_hybrid", fake_extract_hybrid)

    result = run_ingest(
        paths=paths,
        extraction_config=DummyExtractionConfig(),
        artigo_id="ART_001",
        force=True,
        dry_run=False,
    )

    assert result["success"] == 1
