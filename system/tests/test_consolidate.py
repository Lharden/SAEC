from __future__ import annotations

from pathlib import Path

from consolidate import load_yaml


def test_load_yaml_accepts_trailing_document_separator(tmp_path: Path) -> None:
    yaml_path = tmp_path / "ART_001.yaml"
    yaml_path.write_text("ArtigoID: ART_001\nAno: 2025\n---\n", encoding="utf-8")

    data = load_yaml(yaml_path)

    assert data["ArtigoID"] == "ART_001"
    assert data["Ano"] == 2025


def test_load_yaml_returns_empty_when_no_mapping_document(tmp_path: Path) -> None:
    yaml_path = tmp_path / "invalid.yaml"
    yaml_path.write_text("- item-1\n- item-2\n", encoding="utf-8")

    data = load_yaml(yaml_path)

    assert data == {}
