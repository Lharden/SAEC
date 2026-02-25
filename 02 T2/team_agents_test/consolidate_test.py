"""
Consolidação dos YAMLs aprovados em Excel final.

Uso:
    python consolidate_test.py --yamls ./yamls --qa-report ./qa_report.csv --output ./extracoes_final.xlsx
    python consolidate_test.py --yamls ./yamls --output ./extracoes_final.xlsx --all
"""
import argparse
import csv
import logging
import sys
from pathlib import Path

import yaml

# Adiciona SAEC system/src ao path para reutilizar flatten_extraction
_ROOT = Path(__file__).resolve().parent.parent.parent
_SAEC_SRC = _ROOT / "system" / "src"
sys.path.insert(0, str(_SAEC_SRC))

try:
    from consolidate import load_yaml, flatten_extraction
    _CONSOLIDATE_AVAILABLE = True
except ImportError:
    _CONSOLIDATE_AVAILABLE = False

log = logging.getLogger(__name__)


def _load_yaml_simple(yaml_path: Path) -> dict:
    """Fallback: carrega YAML sem dependências do SAEC."""
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _flatten_simple(data: dict) -> dict:
    """Fallback: achata YAML para linha de DataFrame sem dependências do SAEC."""
    row: dict = {}

    simple_fields = [
        "ArtigoID", "Ano", "TipoPublicação", "Referência_Curta", "DOI",
        "SegmentoO&G", "SegmentoO&G_Confiança", "Ambiente", "Complexidade",
        "Complexidade_Justificativa", "ProcessoSCM_Alvo", "TipoRisco_SCRM",
        "ObjetoCrítico", "ClasseIA", "ClasseIA_Confiança", "TarefaAnalítica",
        "FamíliaModelo", "TipoDado", "Maturidade", "Maturidade_Confiança",
        "CategoriaMecanismo", "Mecanismo_Fonte", "Mecanismo_Estruturado",
        "ResultadoTipo", "Resultados_Quant", "NívelEvidência",
    ]
    for field in simple_fields:
        row[field] = data.get(field, "")

    narrative_fields = [
        "ProblemaNegócio_Contexto", "Intervenção_Descrição", "Dados_Descrição",
        "Mecanismo_Declarado", "Mecanismo_Inferido", "Resultados_Qual",
        "Limitações_Artigo", "Observação",
    ]
    for field in narrative_fields:
        val = data.get(field, "") or ""
        row[field] = " ".join(str(val).split()) if val else ""

    quotes = data.get("Quotes", []) or []
    row["Quotes_Resumo"] = " | ".join(
        f"[{q.get('TipoQuote', '?')}] {str(q.get('Trecho', ''))[:80]}"
        for q in quotes[:5]
        if isinstance(q, dict)
    )

    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida YAMLs extraídos em Excel")
    parser.add_argument("--yamls", required=True, help="Diretório com os YAMLs")
    parser.add_argument("--qa-report", help="CSV do QA para filtrar apenas aprovados")
    parser.add_argument("--output", default="extracoes_final.xlsx", help="Arquivo Excel de saída")
    parser.add_argument("--all", action="store_true", help="Incluir todos (ignorar filtro QA)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()],
    )

    try:
        import pandas as pd
    except ImportError:
        log.error("pandas não instalado. Execute: pip install pandas openpyxl")
        return 1

    # Determinar funções de carregamento
    if _CONSOLIDATE_AVAILABLE:
        log.info("Usando consolidate.py do SAEC (flatten completo)")
        _load = load_yaml
        _flatten = flatten_extraction
    else:
        log.warning(f"consolidate.py não disponível em {_SAEC_SRC} — usando fallback simplificado")
        _load = _load_yaml_simple
        _flatten = _flatten_simple

    # Filtro QA
    approved_ids: set[str] | None = None
    if args.qa_report and not args.all:
        qa_path = Path(args.qa_report)
        if not qa_path.exists():
            log.error(f"QA report não encontrado: {qa_path}")
            return 1
        approved_ids = set()
        with open(qa_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("Status") == "APROVADO":
                    approved_ids.add(row["ArtigoID"])
        log.info(f"Filtro QA ativo: {len(approved_ids)} artigos aprovados")

    # Processar YAMLs
    yamls_dir = Path(args.yamls)
    yaml_files = sorted(yamls_dir.glob("ART_*.yaml"))

    if not yaml_files:
        log.warning(f"Nenhum YAML encontrado em {yamls_dir}")
        return 0

    rows = []
    skipped = 0

    for yaml_path in yaml_files:
        article_id = yaml_path.stem

        if approved_ids is not None and article_id not in approved_ids:
            log.debug(f"Pulando {article_id} (não aprovado no QA)")
            skipped += 1
            continue

        try:
            data = _load(yaml_path)
            if not isinstance(data, dict):
                log.warning(f"{article_id}: YAML não é dicionário, pulando")
                skipped += 1
                continue
            flat = _flatten(data)
            rows.append(flat)
            log.info(f"+ {article_id}")
        except Exception as exc:
            log.warning(f"Erro ao processar {article_id}: {exc}")
            skipped += 1

    if not rows:
        log.warning("Nenhum artigo consolidado")
        return 0

    # Gerar Excel
    df = pd.DataFrame(rows)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        df.to_excel(output_path, index=False, engine="openpyxl")
    except ImportError:
        log.error("openpyxl não instalado. Execute: pip install openpyxl")
        return 1

    log.info("")
    log.info("=" * 50)
    log.info(f"Consolidados: {len(rows)} artigos | Pulados: {skipped}")
    log.info(f"Excel salvo: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
