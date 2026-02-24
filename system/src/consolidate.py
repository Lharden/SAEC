"""Consolidação de YAMLs em Excel."""

import importlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Set, cast

import pandas as pd
import yaml


def _load_validators():
    try:
        return importlib.import_module(".validators", package=__package__)
    except (ImportError, ModuleNotFoundError, TypeError):  # pragma: no cover - standalone usage
        return importlib.import_module("validators")


_validators = _load_validators()
_validate_yaml_file = _validators.validate_yaml_file


def _load_profile_engine():
    try:
        return importlib.import_module(".profile_engine", package=__package__)
    except (ImportError, ModuleNotFoundError, TypeError):  # pragma: no cover - standalone usage
        try:
            return importlib.import_module("profile_engine")
        except (ImportError, ModuleNotFoundError):
            return None


_profile_engine = _load_profile_engine()

def _load_qa_ok_ids(qa_report_path: Path) -> Set[str]:
    try:
        mod = importlib.import_module(".qa_utils", package=__package__)
    except (ImportError, ModuleNotFoundError, TypeError):  # pragma: no cover - standalone usage
        mod = importlib.import_module("qa_utils")
    return mod.load_qa_ok_ids(qa_report_path)

# Configurar logger
logger = logging.getLogger(__name__)


def load_yaml(yaml_path: Path) -> dict:
    """Carrega um arquivo YAML."""
    raw = yaml_path.read_text(encoding="utf-8", errors="replace")
    docs = list(yaml.safe_load_all(raw))
    for doc in docs:
        if isinstance(doc, dict):
            return doc
    return {}


def flatten_extraction(data: dict) -> dict:
    """
    Achata estrutura do YAML para linha de DataFrame.

    Converte campos aninhados e listas em strings.
    """
    flat: dict[str, Any] = {}

    profile_fields = _resolve_runtime_profile_fields()
    if profile_fields:
        return _flatten_dynamic_by_profile(data, profile_fields)

    # Campos simples (copiar diretamente) - fallback legacy CIMO
    simple_fields = [
        "ArtigoID", "Ano", "TipoPublicação", "Referência_Curta", "DOI",
        "SegmentoSetorial", "SegmentoSetorial_Confiança", "Ambiente", "Complexidade",
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


def _flatten_dynamic_by_profile(data: dict, field_ids: list[str]) -> dict:
    flat: dict[str, Any] = {}
    for field in field_ids:
        value = data.get(field, "")
        if isinstance(value, (list, dict)):
            flat[field] = yaml.safe_dump(
                value,
                allow_unicode=True,
                sort_keys=False,
            ).strip()
        elif value is None:
            flat[field] = ""
        else:
            flat[field] = str(value).strip()

    quotes = data.get("Quotes", [])
    if isinstance(quotes, list):
        flat["Quotes_Count"] = len(quotes)
        quotes_summary: list[str] = []
        for q in quotes[:5]:
            if not isinstance(q, dict):
                continue
            tipo = q.get("TipoQuote", "?")
            trecho = str(q.get("Trecho", ""))[:80]
            pagina = q.get("Página", "")
            quotes_summary.append(f"[{tipo}|{pagina}] {trecho}...")
        flat["Quotes_Summary"] = " || ".join(quotes_summary)
    else:
        flat["Quotes_Count"] = 0
        flat["Quotes_Summary"] = ""
    return flat


def _resolve_runtime_profile_fields() -> list[str]:
    if _profile_engine is None:
        return []
    try:
        project_root = _profile_engine.resolve_runtime_project_root()
    except (ImportError, ModuleNotFoundError, AttributeError, OSError):
        return []
    if project_root is None:
        return []
    try:
        spec, _ref = _profile_engine.load_active_profile_spec(project_root)
    except (ImportError, ModuleNotFoundError, AttributeError, OSError):
        return []
    return [field.field_id for field in spec.fields]


def _discover_yaml_files(yamls_dir: Path) -> list[Path]:
    yaml_files = sorted(yamls_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"[WARN] Nenhum YAML encontrado em {yamls_dir}")
        return []
    print(f"[INFO] Processando {len(yaml_files)} arquivos YAML...")
    return yaml_files


def _resolve_qa_filter_ids(qa_report_path: Path | None) -> Set[str] | None:
    if qa_report_path is None:
        return None
    if not qa_report_path.exists():
        raise FileNotFoundError(f"QA report not found: {qa_report_path}")
    return _load_qa_ok_ids(qa_report_path)


def _collect_rows_and_validation(
    yaml_files: list[Path],
    *,
    only_valid: bool,
    require_qa_ok: bool,
    qa_ok_ids: Set[str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    validation_results: list[dict[str, Any]] = []

    for yaml_path in yaml_files:
        artigo_id = yaml_path.stem
        try:
            data = load_yaml(yaml_path)
            validation = _validate_yaml_file(yaml_path)
            validation_results.append(
                {
                    "ArtigoID": artigo_id,
                    "Válido": "Sim" if validation.is_valid else "Não",
                    "Erros": len(validation.errors),
                    "Avisos": len(validation.warnings),
                    "Detalhes": "; ".join(validation.errors[:3]),
                }
            )

            if only_valid and not validation.is_valid:
                print(f"  [SKIP] {artigo_id}: {len(validation.errors)} erros de validação")
                continue

            if require_qa_ok:
                if qa_ok_ids is None:
                    raise ValueError("require_qa_ok=True exige qa_report_path")
                if artigo_id not in qa_ok_ids:
                    print(f"  [SKIP] {artigo_id}: QA != OK")
                    continue

            flat = flatten_extraction(data)
            flat["_source_file"] = yaml_path.name
            flat["_valid"] = validation.is_valid
            rows.append(flat)
        except (yaml.YAMLError, ValueError, KeyError, TypeError) as e:
            errors.append({"ArtigoID": artigo_id, "Erro": str(e)[:200]})
            print(f"  [ERRO] {artigo_id}: {e}")

    return rows, errors, validation_results


def _collect_quotes_rows(yaml_files: list[Path]) -> list[dict[str, Any]]:
    quotes_rows: list[dict[str, Any]] = []
    for yaml_path in yaml_files:
        try:
            data = load_yaml(yaml_path)
            for quote in data.get("Quotes", []):
                quotes_rows.append(
                    {
                        "ArtigoID": data.get("ArtigoID", yaml_path.stem),
                        "QuoteID": quote.get("QuoteID", ""),
                        "TipoQuote": quote.get("TipoQuote", ""),
                        "Trecho": quote.get("Trecho", ""),
                        "Página": quote.get("Página", ""),
                    }
                )
        except (yaml.YAMLError, ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to load quotes from %s: %s", yaml_path.name, e)
    return quotes_rows


def _build_metadata(total_files: int, consolidated_rows: int, error_rows: int) -> pd.DataFrame:
    metadata_rows = [
        {"Campo": "Data Consolidação", "Valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Campo": "Total Arquivos", "Valor": total_files},
        {"Campo": "Artigos Consolidados", "Valor": consolidated_rows},
        {"Campo": "Artigos com Erro", "Valor": error_rows},
        {"Campo": "Versão Guia", "Valor": "v3.3"},
        {"Campo": "Sistema", "Valor": "SAEC v1.0"},
    ]
    return pd.DataFrame(metadata_rows)


def _write_excel_outputs(
    output_excel: Path,
    *,
    exported_rows: pd.DataFrame,
    quotes_rows: list[dict[str, Any]],
    validation_results: list[dict[str, Any]],
    metadata_df: pd.DataFrame,
) -> None:
    output_excel.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        exported_rows.to_excel(writer, sheet_name="Extrações", index=False)
        if quotes_rows:
            pd.DataFrame(quotes_rows).to_excel(writer, sheet_name="Quotes", index=False)
        if validation_results:
            pd.DataFrame(validation_results).to_excel(
                writer, sheet_name="Validação", index=False
            )
        metadata_df.to_excel(writer, sheet_name="Metadata", index=False)


def _write_audit_csv(output_audit: Path | None, validation_results: list[dict[str, Any]]) -> None:
    if output_audit is None:
        return
    pd.DataFrame(validation_results).to_csv(output_audit, index=False, encoding="utf-8")
    print(f"[OK] Auditoria: {output_audit}")


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
    yaml_files = _discover_yaml_files(yamls_dir)
    if not yaml_files:
        return pd.DataFrame()

    qa_ok_ids = _resolve_qa_filter_ids(qa_report_path)
    rows, errors, validation_results = _collect_rows_and_validation(
        yaml_files,
        only_valid=only_valid,
        require_qa_ok=require_qa_ok,
        qa_ok_ids=qa_ok_ids,
    )

    df = pd.DataFrame(rows)
    if df.empty:
        print("[WARN] Nenhum dado para consolidar")
        return df

    if "ArtigoID" in df.columns:
        df = df.sort_values("ArtigoID")

    df_export = df.drop(columns=["_source_file", "_valid"], errors="ignore")
    quotes_rows = _collect_quotes_rows(yaml_files)
    metadata_df = _build_metadata(
        total_files=len(yaml_files),
        consolidated_rows=len(df),
        error_rows=len(errors),
    )
    _write_excel_outputs(
        output_excel,
        exported_rows=df_export,
        quotes_rows=quotes_rows,
        validation_results=validation_results,
        metadata_df=metadata_df,
    )

    print(f"[OK] Excel gerado: {output_excel}")
    print(f"     {len(df)} artigos consolidados")
    _write_audit_csv(output_audit, validation_results)
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
        "SegmentoSetorial", "Ambiente", "Complexidade", "ClasseIA",
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


