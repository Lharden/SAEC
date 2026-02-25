"""
Validação QA dos YAMLs extraídos contra as 12 regras do Guia v3.3.

Uso:
    python qa_validate.py --yamls ./yamls --output ./qa_report.csv
"""
import argparse
import csv
import json
import logging
import sys
from pathlib import Path

# Paths: script em 02 T2/team_agents_test → .parent×3 chega em 00 Dados RSL
_ROOT = Path(__file__).resolve().parent.parent  # 00 Dados RSL
_SAEC_SRC = _ROOT / "system" / "src"
sys.path.insert(0, str(_SAEC_SRC))

try:
    from validators import YAMLValidator
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="QA dos YAMLs extraídos via Agent Team")
    parser.add_argument("--yamls", required=True, help="Diretório com os YAMLs extraídos")
    parser.add_argument("--output", default="qa_report.csv", help="Arquivo CSV de saída")
    parser.add_argument("--metas", help="Diretório com .meta.json (padrão: mesmo que --yamls)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()],
    )

    if not VALIDATOR_AVAILABLE:
        log.error(f"Não foi possível importar YAMLValidator de {_SAEC_SRC}")
        log.error("Verifique se o SAEC system/src está acessível e as dependências instaladas.")
        return 1

    yamls_dir = Path(args.yamls)
    if not yamls_dir.exists():
        log.error(f"Diretório não encontrado: {yamls_dir}")
        return 1

    yaml_files = sorted(yamls_dir.glob("ART_*.yaml"))
    if not yaml_files:
        log.warning(f"Nenhum YAML encontrado em {yamls_dir}")
        return 0

    log.info(f"Validando {len(yaml_files)} YAMLs...")

    metas_dir = Path(args.metas) if args.metas else yamls_dir
    validator = YAMLValidator()
    rows = []

    for yaml_path in yaml_files:
        article_id = yaml_path.stem

        # Carregar metadata do modelo se disponível
        model_used = "desconhecido"
        meta_path = metas_dir / f"{article_id}.meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                model_used = meta.get("model", "desconhecido")
            except (json.JSONDecodeError, OSError):
                pass

        try:
            result = validator.validate_file(yaml_path)
        except Exception as exc:
            log.error(f"Erro ao validar {article_id}: {exc}")
            rows.append({
                "ArtigoID": article_id,
                "Modelo": model_used,
                "Status": "ERRO",
                "Regras_Passaram": "",
                "Regras_Falharam": "",
                "Erros": str(exc),
                "Avisos": "",
                "Total_Erros": 1,
                "Total_Avisos": 0,
            })
            continue

        symbol = "✓" if result.is_valid else "✗"
        log.info(
            f"{symbol} {article_id} [{model_used}] — "
            f"{len(result.errors)} erros, {len(result.warnings)} avisos"
        )

        if result.errors:
            for err in result.errors:
                log.debug(f"  ERRO: {err}")

        rows.append({
            "ArtigoID": article_id,
            "Modelo": model_used,
            "Status": "APROVADO" if result.is_valid else "REPROVADO",
            "Regras_Passaram": ",".join(str(r) for r in result.rules_passed),
            "Regras_Falharam": ",".join(str(r) for r in result.rules_failed),
            "Erros": " | ".join(result.errors) if result.errors else "",
            "Avisos": " | ".join(result.warnings) if result.warnings else "",
            "Total_Erros": len(result.errors),
            "Total_Avisos": len(result.warnings),
        })

    # Salvar CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    # Resumo
    aprovados = sum(1 for r in rows if r["Status"] == "APROVADO")
    reprovados = sum(1 for r in rows if r["Status"] == "REPROVADO")
    erros = sum(1 for r in rows if r["Status"] == "ERRO")

    log.info("")
    log.info("=" * 50)
    log.info(f"RESUMO QA: {aprovados} aprovados | {reprovados} reprovados | {erros} erros")
    log.info(f"Relatório salvo: {output_path}")

    # Por modelo
    modelos: dict[str, dict] = {}
    for r in rows:
        m = r["Modelo"]
        if m not in modelos:
            modelos[m] = {"aprovados": 0, "total": 0}
        modelos[m]["total"] += 1
        if r["Status"] == "APROVADO":
            modelos[m]["aprovados"] += 1

    log.info("")
    log.info("Por modelo:")
    for modelo, stats in sorted(modelos.items()):
        pct = stats["aprovados"] / stats["total"] * 100
        log.info(f"  {modelo}: {stats['aprovados']}/{stats['total']} ({pct:.0f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
