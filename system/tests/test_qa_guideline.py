from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import qa_guideline as mod


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


def _write_yaml(paths: SimpleNamespace, article_id: str, body: str) -> Path:
    path = paths.YAMLS / f"{article_id}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _write_texts(paths: SimpleNamespace, article_id: str, pages: dict[str, str]) -> None:
    work_dir = paths.WORK / article_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "texts.json").write_text(json.dumps(pages), encoding="utf-8")


def test_is_placeholder_quote_detects_short_or_nr() -> None:
    assert mod._is_placeholder_quote("NR")
    assert mod._is_placeholder_quote("n/a")
    assert mod._is_placeholder_quote("curto")
    assert mod._is_placeholder_quote("conteudo longo e real") is False


def test_audit_yaml_file_returns_ok_for_good_match(monkeypatch, tmp_path: Path) -> None:
    paths = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "_resolve_runtime_critical_fields", lambda: ["ArtigoID"])

    yaml_path = _write_yaml(
        paths,
        "ART_010",
        (
            "---\n"
            "ArtigoID: ART_010\n"
            "Quotes:\n"
            "  - QuoteID: Q001\n"
            "    TipoQuote: Contexto\n"
            "    Trecho: We propose a demand forecasting model for supply chains.\n"
            "    Página: p.1\n"
            "  - QuoteID: Q002\n"
            "    TipoQuote: Outcome\n"
            "    Trecho: Results show a substantial reduction in stockouts.\n"
            "    Página: p.2\n"
            "---\n"
        ),
    )
    _write_texts(
        paths,
        "ART_010",
        {
            "1": "We propose a demand forecasting model for supply chains.",
            "2": "Results show a substantial reduction in stockouts.",
        },
    )

    out = mod.audit_yaml_file(yaml_path, threshold=80.0)

    assert out["status"] == "OK"
    assert out["quotes_match_rate"] == 1.0
    assert out["has_texts_json"] is True


def test_audit_yaml_file_returns_fail_for_low_match_rate(monkeypatch, tmp_path: Path) -> None:
    paths = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "_resolve_runtime_critical_fields", lambda: ["ArtigoID"])

    yaml_path = _write_yaml(
        paths,
        "ART_011",
        (
            "---\n"
            "ArtigoID: ART_011\n"
            "Quotes:\n"
            "  - QuoteID: Q001\n"
            "    TipoQuote: Contexto\n"
            "    Trecho: totally unrelated quote text\n"
            "    Página: p.1\n"
            "---\n"
        ),
    )
    _write_texts(paths, "ART_011", {"1": "real page content without overlap"})

    out = mod.audit_yaml_file(yaml_path, threshold=90.0)

    assert out["status"] == "FAIL"
    assert "match_rate" in out["reasons"]


def test_run_qa_exports_report(monkeypatch, tmp_path: Path) -> None:
    paths = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(mod, "_resolve_runtime_critical_fields", lambda: ["ArtigoID"])
    _write_yaml(
        paths,
        "ART_012",
        (
            "---\n"
            "ArtigoID: ART_012\n"
            "Quotes:\n"
            "  - QuoteID: Q001\n"
            "    TipoQuote: Outro\n"
            "    Trecho: placeholder quote\n"
            "    Página: p.NR\n"
            "---\n"
        ),
    )

    df, report = mod.run_qa(threshold=80.0, export=True)

    assert len(df) == 1
    assert report is not None
    assert report.exists()

