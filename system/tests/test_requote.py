from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import requote_from_texts as mod


def _patch_paths(monkeypatch, tmp_path: Path) -> SimpleNamespace:
    paths = SimpleNamespace(
        YAMLS=tmp_path / "yamls",
        WORK=tmp_path / "work",
        CONSOLIDATED=tmp_path / "consolidated",
    )
    paths.YAMLS.mkdir(parents=True, exist_ok=True)
    paths.WORK.mkdir(parents=True, exist_ok=True)
    paths.CONSOLIDATED.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mod, "paths", paths)
    return paths


def _write_article(paths: SimpleNamespace, article_id: str, yaml_content: str, texts: dict[str, str]) -> None:
    (paths.YAMLS / f"{article_id}.yaml").write_text(yaml_content, encoding="utf-8")
    work_dir = paths.WORK / article_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "texts.json").write_text(json.dumps(texts), encoding="utf-8")


def test_split_sentences_filters_short_lines() -> None:
    text = "short. This is a long enough sentence for candidate extraction."
    result = mod._split_sentences(text)
    assert len(result) == 1
    assert "candidate extraction" in result[0]


def test_requote_one_updates_yaml_quotes(monkeypatch, tmp_path: Path) -> None:
    paths = _patch_paths(monkeypatch, tmp_path)
    yaml_content = (
        "---\n"
        "ArtigoID: ART_001\n"
        "Quotes:\n"
        "  - QuoteID: Q001\n"
        "    TipoQuote: Outro\n"
        "    Trecho: NR\n"
        "    Página: p.NR\n"
        "---\n"
    )
    texts = {
        "1": "We propose an approach for supply chain risk management. The results improved by 20 percent.",
        "2": "The method uses machine learning with historical disruptions and case study evidence.",
    }
    _write_article(paths, "ART_001", yaml_content, texts)

    changed, msg = mod.requote_one("ART_001")

    assert changed is True
    assert msg == "requote aplicado"
    saved = (paths.YAMLS / "ART_001.yaml").read_text(encoding="utf-8")
    assert "TipoQuote" in saved
    assert "Página: p." in saved


def test_fill_pages_force_file_pages(monkeypatch, tmp_path: Path) -> None:
    paths = _patch_paths(monkeypatch, tmp_path)
    yaml_content = (
        "---\n"
        "ArtigoID: ART_002\n"
        "Quotes:\n"
        "  - QuoteID: Q001\n"
        "    TipoQuote: Outcome\n"
        "    Trecho: Significant improvements in prediction accuracy were observed\n"
        "    Página: p.NR\n"
        "---\n"
    )
    texts = {"4": "Significant improvements in prediction accuracy were observed across test sets."}
    _write_article(paths, "ART_002", yaml_content, texts)

    changed, msg = mod.fill_pages("ART_002", force_file_pages=True)

    assert changed is True
    assert "pages normalizadas" in msg
    saved = (paths.YAMLS / "ART_002.yaml").read_text(encoding="utf-8")
    assert "Página: p.4" in saved


def test_requote_failed_returns_empty_log_when_no_fail(monkeypatch, tmp_path: Path) -> None:
    paths = _patch_paths(monkeypatch, tmp_path)
    qa_df = pd.DataFrame([{"ArtigoID": "ART_001", "status": "OK"}])

    out_df, out_path = mod.requote_failed(qa_df)

    assert out_df.empty
    assert out_path.parent == paths.CONSOLIDATED
    assert out_path.exists()

