from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pipeline_extract import run_extract


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
        self.GUIA_PROMPT = root / "guia.md"


def _write_mapping(mapping_path: Path, artigo_id: str, filename: str) -> None:
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"])
        writer.writeheader()
        writer.writerow({"ArtigoID": artigo_id, "Arquivo": filename, "Processado": "Não", "Status": ""})


def test_run_extract_with_mocked_processor(monkeypatch, tmp_path: Path):
    paths = DummyPaths(tmp_path)
    paths.WORK.mkdir(parents=True, exist_ok=True)
    paths.YAMLS.mkdir(parents=True, exist_ok=True)
    paths.GUIA_PROMPT.write_text("prompt", encoding="utf-8")

    _write_mapping(paths.MAPPING_CSV, "ART_001", "paper.pdf")

    work_dir = paths.WORK / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "hybrid.json").write_text(json.dumps({"pages_info": []}), encoding="utf-8")

    class DummyProcessor:
        def __init__(self, *args, **kwargs):
            pass

        def process_article(self, *, artigo_id, hybrid_meta, work_dir, provider=None):
            return (
                "---\nArtigoID: \"ART_001\"\nAno: 2024\nTipoPublicação: \"Journal\"\nReferência_Curta: \"X\"\n"
                "SegmentoSetorial: \"NR\"\nSegmentoSetorial_Confiança: \"Alta\"\nAmbiente: \"NR\"\nComplexidade: \"NR\"\n"
                "Complexidade_Justificativa: \"F1=0 F2=0 F3=0\"\nProcessoSCM_Alvo: \"X\"\n"
                "TipoRisco_SCRM: \"NR\"\nProblemaNegócio_Contexto: \"AAA\\nBBB\\nCCC\"\nClasseIA: \"NR\"\n"
                "ClasseIA_Confiança: \"Alta\"\nTarefaAnalítica: \"NR\"\nFamíliaModelo: \"X\"\nTipoDado: \"NR\"\n"
                "Maturidade: \"NR\"\nMaturidade_Confiança: \"Alta\"\nIntervenção_Descrição: \"AAAA\"\n"
                "Dados_Descrição: \"BBBB\"\nCategoriaMecanismo: \"NR\"\nMecanismo_Fonte: \"NR\"\n"
                "Mecanismo_Declarado: \"X\"\nMecanismo_Estruturado: \"A → B\"\nResultadoTipo: \"NR\"\n"
                "NívelEvidência: \"NR\"\nLimitações_Artigo: \"NR\"\nQuotes:\n"
                "  - QuoteID: Q001\n    TipoQuote: \"Outro\"\n    Trecho: \"AAAAAAAAAA\"\n    Página: \"p.1\"\n"
                "  - QuoteID: Q002\n    TipoQuote: \"Outro\"\n    Trecho: \"BBBBBBBBBB\"\n    Página: \"p.1\"\n"
                "  - QuoteID: Q003\n    TipoQuote: \"Outro\"\n    Trecho: \"CCCCCCCCCC\"\n    Página: \"p.1\"\n---\n",
                type("R", (), {"is_valid": True})(),
            )

    import pipeline_extract as mod

    monkeypatch.setattr(mod, "ArticleProcessor", DummyProcessor)

    result = run_extract(
        paths=paths,
        client=object(),
        guia_path=paths.GUIA_PROMPT,
        output_dir=paths.YAMLS,
        artigo_id="ART_001",
        dry_run=False,
    )

    assert result["success"] == 1


def test_run_extract_reprocesses_existing_yaml_when_force_true(
    monkeypatch, tmp_path: Path
) -> None:
    paths = DummyPaths(tmp_path)
    paths.WORK.mkdir(parents=True, exist_ok=True)
    paths.YAMLS.mkdir(parents=True, exist_ok=True)
    paths.GUIA_PROMPT.write_text("prompt", encoding="utf-8")

    _write_mapping(paths.MAPPING_CSV, "ART_001", "paper.pdf")

    work_dir = paths.WORK / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "hybrid.json").write_text(json.dumps({"pages_info": []}), encoding="utf-8")

    yaml_path = paths.YAMLS / "ART_001.yaml"
    yaml_path.write_text("---\nold: true\n---\n", encoding="utf-8")

    class DummyProcessor:
        def __init__(self, *args, **kwargs):
            pass

        def process_article(self, *, artigo_id, hybrid_meta, work_dir, provider=None):
            return ("---\nArtigoID: ART_001\nforce: true\n---\n", type("R", (), {"is_valid": True})())

    import pipeline_extract as mod

    monkeypatch.setattr(mod, "ArticleProcessor", DummyProcessor)

    result = run_extract(
        paths=paths,
        client=object(),
        guia_path=paths.GUIA_PROMPT,
        output_dir=paths.YAMLS,
        artigo_id="ART_001",
        force=True,
        dry_run=False,
    )

    assert result["success"] == 1
    assert "force: true" in yaml_path.read_text(encoding="utf-8")


def test_run_extract_article_with_existing_yaml_requires_force(tmp_path: Path) -> None:
    paths = DummyPaths(tmp_path)
    paths.WORK.mkdir(parents=True, exist_ok=True)
    paths.YAMLS.mkdir(parents=True, exist_ok=True)
    paths.GUIA_PROMPT.write_text("prompt", encoding="utf-8")

    _write_mapping(paths.MAPPING_CSV, "ART_001", "paper.pdf")

    work_dir = paths.WORK / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "hybrid.json").write_text(json.dumps({"pages_info": []}), encoding="utf-8")
    (paths.YAMLS / "ART_001.yaml").write_text("---\nold: true\n---\n", encoding="utf-8")

    with pytest.raises(ValueError, match="sem force"):
        run_extract(
            paths=paths,
            client=object(),
            guia_path=paths.GUIA_PROMPT,
            output_dir=paths.YAMLS,
            artigo_id="ART_001",
            force=False,
            dry_run=True,
        )

