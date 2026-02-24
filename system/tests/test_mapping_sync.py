from __future__ import annotations

import csv
from pathlib import Path

from config import generate_mapping_csv


def _read_rows(mapping_path: Path) -> list[dict[str, str]]:
    with open(mapping_path, "r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_generate_mapping_creates_rows_for_all_pdfs(tmp_path: Path) -> None:
    articles = tmp_path / "inputs" / "articles"
    articles.mkdir(parents=True)
    (articles / "b.pdf").write_bytes(b"b")
    (articles / "a.pdf").write_bytes(b"a")
    mapping = tmp_path / "mapping.csv"

    generate_mapping_csv(articles_dir=articles, output_path=mapping, overwrite=False)

    rows = _read_rows(mapping)
    assert [row["Arquivo"] for row in rows] == ["a.pdf", "b.pdf"]
    assert [row["ArtigoID"] for row in rows] == ["ART_001", "ART_002"]


def test_generate_mapping_syncs_empty_existing_file(tmp_path: Path) -> None:
    articles = tmp_path / "inputs" / "articles"
    articles.mkdir(parents=True)
    (articles / "paper.pdf").write_bytes(b"x")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("ArtigoID,Arquivo,Processado,Status\n", encoding="utf-8")

    generate_mapping_csv(articles_dir=articles, output_path=mapping, overwrite=False)

    rows = _read_rows(mapping)
    assert len(rows) == 1
    assert rows[0]["Arquivo"] == "paper.pdf"
    assert rows[0]["ArtigoID"] == "ART_001"
    assert mapping.with_suffix(".csv.bak").exists()


def test_generate_mapping_syncs_new_pdfs_and_preserves_existing_rows(tmp_path: Path) -> None:
    articles = tmp_path / "inputs" / "articles"
    articles.mkdir(parents=True)
    (articles / "a.pdf").write_bytes(b"a")
    (articles / "b.pdf").write_bytes(b"b")

    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "ArtigoID,Arquivo,Processado,Status\n"
        "ART_010,a.pdf,Sim,done\n",
        encoding="utf-8",
    )

    generate_mapping_csv(articles_dir=articles, output_path=mapping, overwrite=False)

    rows = _read_rows(mapping)
    assert len(rows) == 2
    assert rows[0]["ArtigoID"] == "ART_010"
    assert rows[0]["Arquivo"] == "a.pdf"
    assert rows[0]["Processado"] == "Sim"
    assert rows[0]["Status"] == "done"
    assert rows[1]["Arquivo"] == "b.pdf"
    assert rows[1]["ArtigoID"] == "ART_011"


def test_generate_mapping_overwrite_resets_article_ids(tmp_path: Path) -> None:
    articles = tmp_path / "inputs" / "articles"
    articles.mkdir(parents=True)
    (articles / "z.pdf").write_bytes(b"z")

    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "ArtigoID,Arquivo,Processado,Status\n"
        "ART_009,z.pdf,Sim,done\n",
        encoding="utf-8",
    )

    generate_mapping_csv(articles_dir=articles, output_path=mapping, overwrite=True)

    rows = _read_rows(mapping)
    assert len(rows) == 1
    assert rows[0]["ArtigoID"] == "ART_001"
    assert rows[0]["Arquivo"] == "z.pdf"
    assert rows[0]["Processado"] == "Não"
