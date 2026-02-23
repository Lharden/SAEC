from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters import marker_adapter as mod
from exceptions import IngestError


def test_build_marker_pages_extracts_basic_flags() -> None:
    markdown = "Text page\n\n---\n\n![img](x)\n|a|b|\n|---|---|"
    pages = mod._build_marker_pages(markdown)

    assert len(pages) == 2
    assert pages[1].has_images is True
    assert pages[1].has_tables is True


def test_convert_pdf_to_markdown_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="PDF não encontrado"):
        mod.convert_pdf_to_markdown(tmp_path / "missing.pdf", tmp_path / "out")


def test_convert_pdf_to_markdown_raises_when_marker_unavailable(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(mod, "is_marker_available", lambda: False)

    with pytest.raises(IngestError, match="marker-pdf não está instalado"):
        mod.convert_pdf_to_markdown(pdf, tmp_path / "out")


def test_convert_pdf_to_markdown_success(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    output_dir = tmp_path / "out"

    rendered = SimpleNamespace(
        markdown="Page one\n\n---\n\nPage two",
        metadata={"k": "v"},
        images={"img1.png": b"123"},
        tables=["table-1"],
    )
    monkeypatch.setattr(mod, "is_marker_available", lambda: True)
    monkeypatch.setattr(mod, "_run_marker_conversion", lambda _path: rendered)

    result = mod.convert_pdf_to_markdown(pdf, output_dir)

    assert result.success is True
    assert result.total_pages == 2
    assert result.metadata["k"] == "v"
    assert len(result.images) == 1
    assert len(result.tables) == 1
    assert (output_dir / "a.md").exists()


def test_analyze_pdf_quality_returns_error_payload_when_fitz_fails(monkeypatch, tmp_path: Path) -> None:
    def _raise_open(_path: object):
        raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=_raise_open))

    out = mod.analyze_pdf_quality(tmp_path / "a.pdf")

    assert out["recommended_strategy"] == "text"
    assert "error" in out
