"""Consolidação de YAMLs em Excel."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Set, cast

import pandas as pd
import yaml

import importlib


def _load_validators():
    try:
        return importlib.import_module(".validators", package=__package__)
    except Exception:  # pragma: no cover - standalone usage
        return importlib.import_module("validators")


_validators = _load_validators()
_validate_yaml_file = _validators.validate_yaml_file

def _load_qa_ok_ids(qa_report_path: Path) -> Set[str]:
    try:
        mod = importlib.import_module(".qa_utils", package=__package__)
    except Exception:  # pragma: no cover - standalone usage
        mod = importlib.import_module("qa_utils")
    return mod.load_qa_ok_ids(qa_report_path)

# Configurar logger
logger = logging.getLogger(__name__)


def load_yaml(yaml_path: Path) -> dict:
    """Carrega um arquivo YAML."""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_extraction(data: dict) -> dict:
    """
    Achata estrutura do YAML para linha de DataFrame.

    Converte campos aninhados e listas em strings.
    """
    flat: dict[str, Any] = {}

    # Campos simples (copiar diretamente)
    simple_fields = [
        "ArtigoID", "Ano", "TipoPublicação", "Referência_Curta", "DOI",
        "SegmentoO&G", "SegmentoO&G_Confiança", "Ambiente", "Complexidade",
        "Complexidade_Justificativa", "ProcessoSCM_Alvo", "TipoRisco_SCRM",
        "ObjetoCrítico", "ClasseIA", "ClasseIA_Confiança", "TarefaAnalítica",
        "FamíliaModelo", "TipoDado", "Maturidade", "Maturidade_Confiança",
        "CategoriaMecanismo", "Mecanismo_Fonte", "Mecanismo_Estruturado",
        "ResultadoTipo", "Resultados_Quant", "Resultados_Qual",
        "NívelEvidência"
    ]

    for field in simple_fields:
        value = data.get(field, "")
        flat[field] = str(value).strip() if value else ""

    # Campos narrativos (normalizar espaços e quebras de linha)
    narrative_fields = [
        "ProblemaNegócio_Contexto", "Intervenção_Descrição", "Dados_Descrição",
        "Mecanismo_Declarado", "Mecanismo_Inferido", "Limitações_Artigo", "Observação"
    ]

    for field in narrative_fields:
        value = data.get(field, "")
        if isinstance(value, str):
            # Normalizar: múltiplos espaços/quebras → espaço único
            normalized = " ".join(value.split())
            flat[field] = normalized
        else:
            flat[field] = str(value) if value else ""

    # Quotes: contar e concatenar resumo
    quotes = data.get("Quotes", [])
    flat["Quotes_Count"] = len(quotes)

    # Criar resumo das quotes (tipo + trecho truncado)
    quotes_summary = []
    for q in quotes[:5]:  # Máximo 5 no resumo
        tipo = q.get("TipoQuote", "?")
        trecho = q.get("Trecho", "")[:80]
        pagina = q.get("Página", "")
        quotes_summary.append(f"[{tipo}|{pagina}] {trecho}...")

    flat["Quotes_Summary"] = " || ".join(quotes_summary)

    return flat


def consolidate_yamls(
    yamls_dir: Path,
    output_excel: Path,
    output_audit: Path | None = None,
    only_valid: bool = True,
    qa_report_path: Optional[Path] = None,
    require_qa_ok: bool = False,
) -> pd.DataFrame:
    """
    Consolida todos os YAMLs em um Excel.

    Args:
        yamls_dir: Diretório com YAMLs
        output_excel: Caminho do Excel de saída
        output_audit: Caminho opcional do CSV de auditoria
        only_valid: Se True, só inclui YAMLs que passam validação

    Returns:
        DataFrame consolidado
    """
    rows = []
    errors = []
    validation_results = []

    yaml_files = sorted(yamls_dir.glob("*.yaml"))

    if not yaml_files:
        print(f"[WARN] Nenhum YAML encontrado em {yamls_dir}")
        return pd.DataFrame()

    print(f"[INFO] Processando {len(yaml_files)} arquivos YAML...")

    qa_ok_ids: Optional[Set[str]] = None
    if qa_report_path:
        if not qa_report_path.exists():
            raise FileNotFoundError(f"QA report not found: {qa_report_path}")
        qa_ok_ids = _load_qa_ok_ids(qa_report_path)

    for yaml_path in yaml_files:
        artigo_id = yaml_path.stem

        try:
            # Carregar YAML
            data = load_yaml(yaml_path)

            # Validar
            validation = _validate_yaml_file(yaml_path)
            validation_results.append({
                "ArtigoID": artigo_id,
                "Válido": "Sim" if validation.is_valid else "Não",
                "Erros": len(validation.errors),
                "Avisos": len(validation.warnings),
                "Detalhes": "; ".join(validation.errors[:3])  # Primeiros 3 erros
            })

            # Se only_valid e não é válido, pular
            if only_valid and not validation.is_valid:
                print(f"  [SKIP] {artigo_id}: {len(validation.errors)} erros de validação")
                continue

            # Se require_qa_ok e não está OK no QA, pular
            if require_qa_ok:
                if qa_ok_ids is None:
                    raise ValueError("require_qa_ok=True exige qa_report_path")
                if artigo_id not in qa_ok_ids:
                    print(f"  [SKIP] {artigo_id}: QA != OK")
                    continue

            # Achatar para linha
            flat = flatten_extraction(data)
            flat["_source_file"] = yaml_path.name
            flat["_valid"] = validation.is_valid
            rows.append(flat)

        except Exception as e:
            errors.append({
                "ArtigoID": artigo_id,
                "Erro": str(e)[:200]
            })
            print(f"  [ERRO] {artigo_id}: {e}")

    # Criar DataFrame principal
    df = pd.DataFrame(rows)

    if df.empty:
        print("[WARN] Nenhum dado para consolidar")
        return df

    # Ordenar por ArtigoID
    if "ArtigoID" in df.columns:
        df = df.sort_values("ArtigoID")

    # Remover colunas internas
    df_export = df.drop(columns=["_source_file", "_valid"], errors="ignore")

    # Salvar Excel
    output_excel.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        # Aba principal: Extrações
        df_export.to_excel(writer, sheet_name="Extrações", index=False)

        # Aba: Quotes expandidas
        quotes_rows = []
        for yaml_path in yaml_files:
            try:
                data = load_yaml(yaml_path)
                for q in data.get("Quotes", []):
                    quotes_rows.append({
                        "ArtigoID": data.get("ArtigoID", yaml_path.stem),
                        "QuoteID": q.get("QuoteID", ""),
                        "TipoQuote": q.get("TipoQuote", ""),
                        "Trecho": q.get("Trecho", ""),
                        "Página": q.get("Página", "")
                    })
            except Exception as e:
                logger.warning(f"Failed to load quotes from {yaml_path.name}: {e}")

        if quotes_rows:
            df_quotes = pd.DataFrame(quotes_rows)
            df_quotes.to_excel(writer, sheet_name="Quotes", index=False)

        # Aba: Validação
        if validation_results:
            df_validation = pd.DataFrame(validation_results)
            df_validation.to_excel(writer, sheet_name="Validação", index=False)

        # Aba: Metadata
        meta_df = pd.DataFrame([{
            "Campo": "Data Consolidação",
            "Valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, {
            "Campo": "Total Arquivos",
            "Valor": len(yaml_files)
        }, {
            "Campo": "Artigos Consolidados",
            "Valor": len(df)
        }, {
            "Campo": "Artigos com Erro",
            "Valor": len(errors)
        }, {
            "Campo": "Versão Guia",
            "Valor": "v3.3"
        }, {
            "Campo": "Sistema",
            "Valor": "SAEC-O&G v1.0"
        }])
        meta_df.to_excel(writer, sheet_name="Metadata", index=False)

    print(f"[OK] Excel gerado: {output_excel}")
    print(f"     {len(df)} artigos consolidados")

    # Salvar auditoria se solicitado
    if output_audit:
        audit_df = pd.DataFrame(validation_results)
        audit_df.to_csv(output_audit, index=False, encoding="utf-8")
        print(f"[OK] Auditoria: {output_audit}")

    return df


def generate_statistics(df: pd.DataFrame) -> dict:
    """
    Gera estatísticas descritivas do DataFrame consolidado.

    Returns:
        Dict com estatísticas por campo categórico
    """
    stats: dict[str, Any] = {
        "total_artigos": len(df),
        "distribuicoes": {}
    }

    # Campos categóricos para estatísticas
    categorical_fields = [
        "SegmentoO&G", "Ambiente", "Complexidade", "ClasseIA",
        "TarefaAnalítica", "Maturidade", "CategoriaMecanismo",
        "ResultadoTipo", "NívelEvidência", "TipoRisco_SCRM"
    ]

    for field in categorical_fields:
        if field in df.columns:
            counts = df[field].value_counts().to_dict()
            stats["distribuicoes"][field] = counts

    # Estatísticas de quotes
    if "Quotes_Count" in df.columns:
        stats["quotes"] = {
            "media": df["Quotes_Count"].mean(),
            "min": df["Quotes_Count"].min(),
            "max": df["Quotes_Count"].max()
        }

    # Anos
    if "Ano" in df.columns:
        anos_series = cast(Any, pd.to_numeric(df["Ano"], errors="coerce"))
        anos_series = anos_series[anos_series.notna()]
        if not anos_series.empty:
            stats["anos"] = {
                "min": int(cast(float, anos_series.min())),
                "max": int(cast(float, anos_series.max())),
                "distribuicao": df["Ano"].value_counts().sort_index().to_dict()
            }

    return stats


def print_statistics(stats: dict):
    """Imprime estatísticas de forma formatada."""
    print("\n" + "=" * 60)
    print("ESTATÍSTICAS DA CONSOLIDAÇÃO")
    print("=" * 60)

    print(f"\nTotal de artigos: {stats['total_artigos']}")

    if "anos" in stats:
        print(f"\nPeríodo: {stats['anos']['min']} - {stats['anos']['max']}")

    print("\nDistribuições:")
    for field, counts in stats.get("distribuicoes", {}).items():
        print(f"\n  {field}:")
        for value, count in sorted(counts.items(), key=lambda x: -x[1])[:5]:
            pct = count / stats["total_artigos"] * 100
            print(f"    {value}: {count} ({pct:.1f}%)")

    if "quotes" in stats:
        q = stats["quotes"]
        print(f"\n  Quotes por artigo: média={q['media']:.1f}, min={q['min']}, max={q['max']}")


# ============================================================
# Teste
# ============================================================

if __name__ == "__main__":
    print("=== Consolidation Module Test ===")
    print("\nFunções disponíveis:")
    print("  - consolidate_yamls(yamls_dir, output_excel)")
    print("  - generate_statistics(df)")
    print("  - print_statistics(stats)")
