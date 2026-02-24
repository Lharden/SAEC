#!/usr/bin/env python3
"""
SAEC - Script Principal de Execução
Executa pipeline completo de extração CIMO sem Jupyter

Uso:
    python main.py --all          # Executar pipeline completo
    python main.py --step 1       # Apenas configuração
    python main.py --step 2       # Apenas ingestão
    python main.py --step 3       # Apenas extração LLM
    python main.py --step 5       # Apenas consolidação
    python main.py --article ART_001  # Processar artigo específico
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# ============================================================================
# SETUP DE PATHS
# ============================================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
SRC_DIR = SCRIPT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ============================================================================
# IMPORTS (após configurar path)
# ============================================================================
from config import paths, llm_config, extraction_config, generate_mapping_csv, load_mapping
from context import make_context
from pipeline_ingest import run_ingest
from pipeline_extract import run_extract
from llm_client import LLMClient
from exceptions import IngestError, ExtractError
from profile_engine.project_profiles import (
    require_project_profile,
    resolve_profile_prompt_path,
    snapshot_active_profile_for_run,
)

# ============================================================================
# CORES PARA TERMINAL
# ============================================================================
class Colors:
    HEADER: str = '\033[95m'
    OKBLUE: str = '\033[94m'
    OKCYAN: str = '\033[96m'
    OKGREEN: str = '\033[92m'
    WARNING: str = '\033[93m'
    FAIL: str = '\033[91m'
    ENDC: str = '\033[0m'
    BOLD: str = '\033[1m'

# Windows: desabilitar cores se não suportado
import platform
if platform.system() == "Windows":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        Colors.HEADER = ''
        Colors.OKBLUE = ''
        Colors.OKCYAN = ''
        Colors.OKGREEN = ''
        Colors.WARNING = ''
        Colors.FAIL = ''
        Colors.ENDC = ''
        Colors.BOLD = ''

def print_header(text: str):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")

def print_ok(text: str):
    print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} {text}")

def print_warn(text: str):
    print(f"{Colors.WARNING}[WARN]{Colors.ENDC} {text}")

def print_error(text: str):
    print(f"{Colors.FAIL}[ERRO]{Colors.ENDC} {text}")

def print_info(text: str):
    print(f"{Colors.OKBLUE}[INFO]{Colors.ENDC} {text}")

# ============================================================================
# ETAPA 1: CONFIGURAÇÃO
# ============================================================================
def step_1_configuracao() -> bool:
    """Configuração inicial do sistema."""
    print_header("ETAPA 1: CONFIGURAÇÃO")

    # Verificar dependências
    print_info("Verificando dependências...")
    deps = {
        "dotenv": "python-dotenv",
        "yaml": "pyyaml",
        "pydantic": "pydantic",
        "fitz": "pymupdf",
        "PIL": "pillow",
        "anthropic": "anthropic",
        "openai": "openai",
        "pandas": "pandas",
        "openpyxl": "openpyxl",
    }

    missing = []
    for module, package in deps.items():
        try:
            __import__(module)
            print_ok(f"{module}")
        except ImportError:
            print_error(f"{module} - pip install {package}")
            missing.append(package)

    if missing:
        print_error(f"Dependências faltando: {' '.join(missing)}")
        print_info("Execute: pip install " + " ".join(missing))
        return False

    # Configurar paths
    print_info("Configurando caminhos...")
    print(f"  Project root: {paths.PROJECT_ROOT}")
    print(f"  Articles: {paths.ARTICLES}")
    print(f"  Extraction: {paths.EXTRACTION}")

    if not paths.ARTICLES.exists():
        print_error(f"Pasta de artigos não encontrada: {paths.ARTICLES}")
        return False

    # Criar diretórios
    paths.ensure_dirs()
    print_ok("Diretórios criados/verificados")

    # Validar APIs
    print_info("Validando configuração de APIs...")
    errors = llm_config.validate()
    if errors:
        for e in errors:
            print_error(e)
        return False
    print_ok("APIs configuradas")

    # Listar PDFs
    pdfs = sorted(paths.ARTICLES.glob("*.pdf"))
    print_info(f"{len(pdfs)} PDFs encontrados")

    # Gerar mapping
    print_info("Gerando mapping.csv...")
    mapping_path = generate_mapping_csv(
        articles_dir=paths.ARTICLES,
        output_path=paths.MAPPING_CSV,
        overwrite=False
    )
    print_ok(f"Mapping: {mapping_path}")

    # Verificar prompt
    if paths.GUIA_PROMPT.exists():
        content = paths.GUIA_PROMPT.read_text(encoding='utf-8')
        print_ok(f"Prompt encontrado: {len(content)} caracteres")
    else:
        print_warn(f"Prompt não encontrado: {paths.GUIA_PROMPT}")

    # Resumo
    import pandas as pd
    df = pd.read_csv(paths.MAPPING_CSV)
    print_ok(f"Total de artigos: {len(df)}")
    print_ok(f"Processados: {len(df[df['Processado'] == 'Sim'])}")
    print_ok(f"Pendentes: {len(df[df['Processado'] != 'Sim'])}")

    return True

# ============================================================================
# ETAPA 2: INGESTÃO
# ============================================================================
def step_2_ingestao(
    artigo_id: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    context=None,
) -> bool:
    """Ingestão de PDFs (texto + imagens)."""
    print_header("ETAPA 2: INGESTÃO DE PDFs")

    ctx = context or make_context()
    mapping = load_mapping(paths.MAPPING_CSV)
    print_info(f"{len(mapping)} artigos no mapping")

    try:
        results = run_ingest(
            paths=ctx.paths,
            extraction_config=ctx.extraction_config,
            artigo_id=artigo_id,
            force=force,
            dry_run=dry_run,
            logger=ctx.logger,
        )
    except IngestError as e:
        print_error(f"Ingestão falhou: {e}")
        return False

    if dry_run:
        print_warn("MODO DRY-RUN - Simulação apenas")
        print_ok(f"Total: {results['total']}")
        return True

    print_header("RESUMO DA INGESTÃO")
    print_ok(f"Sucesso: {results['success']}")
    print_info(f"Cache: {results['cached']}")
    print_error(f"Erros: {results['error']}")

    return results["error"] == 0

# ============================================================================
# ETAPA 3: EXTRAÇÃO LLM
# ============================================================================
def step_3_extracao(
    artigo_id: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    context=None,
) -> bool:
    """Extração de dados com LLM (providers locais/cloud configurados)."""
    print_header("ETAPA 3: EXTRAÇÃO COM LLM")

    profile_root = paths.EXTRACTION if (paths.EXTRACTION / "project.json").exists() else None
    prompt_path = paths.GUIA_PROMPT
    if profile_root is not None:
        ok, message = require_project_profile(profile_root)
        if not ok:
            print_error(message)
            return False
        try:
            prompt_path = resolve_profile_prompt_path(
                profile_root,
                fallback=paths.UNIVERSAL_PROFILE_PROMPT,
            )
        except Exception as exc:
            print_error(f"Falha ao resolver prompt do perfil ativo: {exc}")
            return False
        print_info(f"Perfil carregado: prompt={prompt_path}")

    # Inicializar cliente LLM
    print_info("Inicializando cliente LLM...")
    try:
        ctx = context or make_context()
        client = LLMClient(context=ctx)
        print_ok(f"Cliente pronto (Two-pass: {llm_config.USE_TWO_PASS})")
    except Exception as e:
        print_error(f"Falha ao inicializar LLM: {e}")
        return False

    # Carregar mapping
    mapping = load_mapping(paths.MAPPING_CSV)

    # Filtrar artigos já ingeridos
    ready = []
    for article in mapping:
        aid = article["ArtigoID"]
        hybrid_file = paths.WORK / aid / "hybrid.json"
        yaml_file = paths.YAMLS / f"{aid}.yaml"

        if hybrid_file.exists() and (force or not yaml_file.exists()):
            ready.append(article)

    print_info(f"Artigos prontos para extração: {len(ready)}")

    if artigo_id:
        article = next((a for a in ready if a["ArtigoID"] == artigo_id), None)
        if not article:
            print_error(
                f"Artigo {artigo_id} não encontrado, sem ingestão, ou já processado sem --force"
            )
            return False
        articles_to_process = [article]
    else:
        articles_to_process = ready

    if not articles_to_process:
        print_ok("Nenhum artigo para extrair")
        return True

    if dry_run:
        print_warn("MODO DRY-RUN - Simulação apenas")
        for article in articles_to_process:
            print_info(f"Simulando: {article['ArtigoID']}")
        return True

    try:
        results = run_extract(
            paths=paths,
            client=client,
            guia_path=prompt_path,
            output_dir=paths.YAMLS,
            artigo_id=artigo_id,
            force=force,
            dry_run=dry_run,
            logger=ctx.logger,
        )
    except ExtractError as e:
        print_error(f"Extração falhou: {e}")
        return False

    print_header("RESUMO DA EXTRAÇÃO")
    print_ok(f"Sucesso: {results['success']}")
    print_error(f"Erros: {results['error']}")

    return results["error"] == 0 or results["success"] > 0

# ============================================================================
# ETAPA 5: CONSOLIDAÇÃO
# ============================================================================
def step_5_consolidacao() -> bool:
    """Consolidação de YAMLs em Excel."""
    print_header("ETAPA 5: CONSOLIDAÇÃO")

    from consolidate import consolidate_yamls, generate_statistics, print_statistics

    # Verificar YAMLs
    yamls = list(paths.YAMLS.glob("*.yaml"))
    print_info(f"YAMLs encontrados: {len(yamls)}")

    if not yamls:
        print_warn("Nenhum YAML para consolidar")
        return False

    # Localizar QA report mais recente (sem gerar novos arquivos)
    qa_reports = sorted(paths.CONSOLIDATED.glob("qa_report_*.csv"))
    qa_report_path = qa_reports[-1] if qa_reports else None
    if qa_report_path:
        print_info(f"QA report: {qa_report_path.name}")
    else:
        print_warn("QA report não encontrado; consolidação seguirá sem filtro QA")

    # Arquivos de saída
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_excel = paths.CONSOLIDATED / f"extracoes_{timestamp}.xlsx"
    output_audit = paths.CONSOLIDATED / f"auditoria_{timestamp}.csv"

    print_info(f"Excel: {output_excel.name}")
    print_info(f"Auditoria: {output_audit.name}")

    # Consolidar
    try:
        df = consolidate_yamls(
            yamls_dir=paths.YAMLS,
            output_excel=output_excel,
            output_audit=output_audit,
            only_valid=True,
            qa_report_path=qa_report_path,
            require_qa_ok=bool(qa_report_path),
        )

        if not df.empty:
            # Estatísticas
            stats = generate_statistics(df)
            print_statistics(stats)
            print_ok(f"Consolidação completa: {len(df)} artigos")
            return True
        else:
            print_warn("DataFrame vazio - nenhum dado válido")
            return False

    except Exception as e:
        print_error(f"Erro na consolidação: {e}")
        return False

# ============================================================================
# STATUS GERAL
# ============================================================================
def show_status():
    """Mostra status do sistema."""
    print_header("STATUS DO SISTEMA SAEC")

    # Verificar estrutura
    checks = {
        "Projeto": paths.PROJECT_ROOT.exists(),
        "Artigos": paths.ARTICLES.exists(),
        "Config": paths.EXTRACTION.exists(),
        "Prompt": paths.GUIA_PROMPT.exists() if hasattr(paths, 'GUIA_PROMPT') else False,
        "Mapping": paths.MAPPING_CSV.exists() if hasattr(paths, 'MAPPING_CSV') else False,
    }

    for name, ok in checks.items():
        if ok:
            print_ok(f"{name}")
        else:
            print_error(f"{name}")

    # Contagens
    if paths.ARTICLES.exists():
        pdfs = list(paths.ARTICLES.glob("*.pdf"))
        print_info(f"PDFs: {len(pdfs)}")

    if paths.WORK.exists():
        ingested = len([d for d in paths.WORK.iterdir() if d.is_dir()])
        print_info(f"Ingeridos: {ingested}")

    if paths.YAMLS.exists():
        yamls = list(paths.YAMLS.glob("*.yaml"))
        print_info(f"YAMLs extraídos: {len(yamls)}")

    if paths.CONSOLIDATED.exists():
        excels = list(paths.CONSOLIDATED.glob("*.xlsx"))
        print_info(f"Excels gerados: {len(excels)}")

# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="SAEC - Pipeline de Extração CIMO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
    python main.py --status              # Ver status
    python main.py --step 1              # Configuração
    python main.py --step 2              # Ingestão de todos PDFs
    python main.py --step 2 --article ART_001  # Ingestão de um artigo
    python main.py --step 3              # Extração LLM de todos
    python main.py --step 5              # Consolidação
    python main.py --all                 # Pipeline completo
        """
    )

    parser.add_argument("--status", action="store_true", help="Mostrar status do sistema")
    parser.add_argument("--step", type=int, choices=[1, 2, 3, 5], help="Executar etapa específica")
    parser.add_argument("--all", action="store_true", help="Executar pipeline completo")
    parser.add_argument("--article", type=str, help="Processar artigo específico (ex: ART_001)")
    parser.add_argument("--force", action="store_true", help="Forçar reprocessamento")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem executar")
    parser.add_argument("--log-level", type=str, default="INFO", help="Nível de log (DEBUG/INFO/WARN)")

    args = parser.parse_args()

    if not any([args.status, args.step, args.all]):
        parser.print_help()
        return 0

    context = make_context(log_level=args.log_level)
    project_profile_root = paths.EXTRACTION if (paths.EXTRACTION / "project.json").exists() else None
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    def _enforce_project_profile_if_needed() -> bool:
        if project_profile_root is None:
            return True
        ok, message = require_project_profile(project_profile_root)
        if not ok:
            print_error(message)
            return False
        return True

    def _snapshot_profile_if_needed(command: str) -> bool:
        if project_profile_root is None:
            return True
        try:
            paths.CONSOLIDATED.mkdir(parents=True, exist_ok=True)
            snapshot = snapshot_active_profile_for_run(
                project_profile_root,
                output_root=paths.CONSOLIDATED,
                run_id=run_id,
                command=command,
                force=bool(args.force),
                dry_run=bool(args.dry_run),
            )
            print_info(f"Snapshot de perfil salvo: {snapshot.profile_yaml_path}")
            return True
        except Exception as exc:
            print_error(f"Falha ao salvar snapshot do perfil ativo: {exc}")
            return False

    try:
        if args.status:
            show_status()
            return 0

        if args.all:
            if not _enforce_project_profile_if_needed():
                return 1
            if not _snapshot_profile_if_needed("--all"):
                return 1
            # Pipeline completo
            ok1 = step_1_configuracao()
            if not ok1:
                print_error("Configuração falhou - abortando")
                return 1

            ok2 = step_2_ingestao(
                artigo_id=args.article,
                force=args.force,
                dry_run=args.dry_run,
                context=context,
            )
            if not ok2:
                print_warn("Ingestão com erros - continuando...")

            ok3 = step_3_extracao(
                artigo_id=args.article,
                force=args.force,
                dry_run=args.dry_run,
                context=context,
            )
            if not ok3:
                print_warn("Extração com erros - continuando...")

            ok5 = step_5_consolidacao()

            print_header("PIPELINE COMPLETO FINALIZADO")
            return 0 if (ok1 and ok5) else 1

        elif args.step == 1:
            return 0 if step_1_configuracao() else 1

        elif args.step == 2:
            if not _enforce_project_profile_if_needed():
                return 1
            if not _snapshot_profile_if_needed("--step 2"):
                return 1
            return 0 if step_2_ingestao(
                artigo_id=args.article,
                force=args.force,
                dry_run=args.dry_run,
                context=context,
            ) else 1

        elif args.step == 3:
            if not _enforce_project_profile_if_needed():
                return 1
            if not _snapshot_profile_if_needed("--step 3"):
                return 1
            return 0 if step_3_extracao(
                artigo_id=args.article,
                force=args.force,
                dry_run=args.dry_run,
                context=context,
            ) else 1

        elif args.step == 5:
            if not _enforce_project_profile_if_needed():
                return 1
            if not _snapshot_profile_if_needed("--step 5"):
                return 1
            return 0 if step_5_consolidacao() else 1

        return 0

    except KeyboardInterrupt:
        print("\n\nOperação cancelada pelo usuário")
        return 130
    except Exception as e:
        print_error(f"Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

