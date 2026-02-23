from __future__ import annotations

from pathlib import Path

import postprocess


def test_wrap_to_multiline_splits_text() -> None:
    text = (
        "This sentence explains the first point. "
        "This sentence explains the second point. "
        "This sentence explains the third point."
    )
    wrapped = postprocess._wrap_to_multiline(text, min_lines=3, max_lines=6)
    assert "\n" in wrapped
    assert len([line for line in wrapped.splitlines() if line.strip()]) >= 3


def test_recalculate_complexidade_updates_value() -> None:
    data = {
        "Complexidade": "Baixa",
        "Complexidade_Justificativa": "F1=1; F2=1; F3=1",
    }
    out = postprocess.recalculate_complexidade(data)
    assert out["Complexidade"] == "Alta"


def test_normalize_maturidade_maps_known_value() -> None:
    data = {"Maturidade": "Simulação com dados sintéticos"}
    out = postprocess.normalize_maturidade(data)
    assert out["Maturidade"] == "Protótipo"


def test_postprocess_yaml_returns_original_on_parse_error() -> None:
    raw = "not: [valid"
    assert postprocess.postprocess_yaml(raw) == raw


def test_postprocess_file_writes_output(tmp_path: Path) -> None:
    yaml_path = tmp_path / "in.yaml"
    yaml_path.write_text("---\nComplexidade: Baixa\nComplexidade_Justificativa: \"F1=1 F2=1 F3=1\"\n---\n", encoding="utf-8")
    out_path = tmp_path / "out.yaml"

    result = postprocess.postprocess_file(str(yaml_path), str(out_path))

    assert out_path.exists()
    saved = out_path.read_text(encoding="utf-8")
    assert result == saved
    assert "Complexidade: Alta" in saved

