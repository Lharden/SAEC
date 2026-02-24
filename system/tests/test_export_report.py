from __future__ import annotations

from pathlib import Path

from export_report import export_summary_csv, generate_summary_rows


_SAMPLE_YAML = """
ArtigoID: ART_001
Referência_Curta: Sample Study
ProblemaNegócio_Contexto: Context text
Intervenção_Descrição: Intervention text
Mecanismo_Estruturado: Mechanism text
Resultados_Quant: 95% accuracy
"""


def test_generate_summary_rows_extracts_core_fields(tmp_path: Path) -> None:
    yamls = tmp_path / "yamls"
    yamls.mkdir()
    (yamls / "ART_001.yaml").write_text(_SAMPLE_YAML, encoding="utf-8")

    rows = generate_summary_rows(yamls)

    assert len(rows) == 1
    row = rows[0]
    assert row["Article ID"] == "ART_001"
    assert row["Title"] == "Sample Study"
    assert row["Status"] == "complete"
    assert row["C count"] == "1"
    assert row["I count"] == "1"
    assert row["M count"] == "1"
    assert row["O count"] == "1"


def test_export_summary_csv_writes_file(tmp_path: Path) -> None:
    yamls = tmp_path / "yamls"
    yamls.mkdir()
    (yamls / "ART_001.yaml").write_text(_SAMPLE_YAML, encoding="utf-8")

    output = tmp_path / "report.csv"
    count = export_summary_csv(yamls, output)

    assert count == 1
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "Article ID" in content
    assert "ART_001" in content


def test_generate_summary_rows_handles_trailing_yaml_separator(tmp_path: Path) -> None:
    yamls = tmp_path / "yamls"
    yamls.mkdir()
    multi_doc = _SAMPLE_YAML.strip() + "\n---\n"
    (yamls / "ART_001.yaml").write_text(multi_doc, encoding="utf-8")

    rows = generate_summary_rows(yamls)

    assert len(rows) == 1
    assert rows[0]["Status"] == "complete"
