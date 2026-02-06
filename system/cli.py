#!/usr/bin/env python3
"""
SAEC-O&G CLI - Interface de linha de comando unificada.

Comandos disponíveis:
    saec status          - Mostra status do sistema
    saec check           - Verifica dependências
    saec ingest          - Ingere PDFs (converte para texto)
    saec extract         - Extrai dados CIMO
    saec validate        - Valida YAMLs extraídos
    saec consolidate     - Consolida YAMLs em Excel
    saec run             - Executa pipeline completo

Uso:
    python cli.py [COMMAND] [OPTIONS]
    python -m system.cli [COMMAND] [OPTIONS]
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Adicionar system/src ao path
sys.path.insert(0, str(Path(__file__).parent))

app = typer.Typer(
    name="saec",
    help="SAEC-O&G - Sistema Autônomo de Extração CIMO",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()


# ============================================================
# Comandos de Status
# ============================================================

@app.command()
def status():
    """Mostra status do sistema e configuração."""
    from src.config import paths, llm_config, local_config

    console.print(Panel.fit("[bold blue]SAEC-O&G Status[/bold blue]"))

    # Paths
    table = Table(title="Caminhos", show_header=True)
    table.add_column("Item", style="cyan")
    table.add_column("Caminho", style="white")
    table.add_column("Existe", style="green")

    table.add_row("Project Root", str(paths.PROJECT_ROOT), "OK" if paths.PROJECT_ROOT.exists() else "NO")
    table.add_row("Articles", str(paths.ARTICLES), "OK" if paths.ARTICLES.exists() else "NO")
    table.add_row("Work Dir", str(paths.WORK), "OK" if paths.WORK.exists() else "NO")
    table.add_row("YAMLs", str(paths.YAMLS), "OK" if paths.YAMLS.exists() else "NO")

    console.print(table)

    # LLM Config
    keys = llm_config.get_masked_keys()
    table2 = Table(title="Configuração LLM", show_header=True)
    table2.add_column("Provider", style="cyan")
    table2.add_column("Status", style="white")

    table2.add_row("Anthropic", keys["anthropic"])
    table2.add_row("OpenAI", keys["openai"])
    table2.add_row("Ollama", keys["ollama"])

    console.print(table2)

    # Local Config
    table3 = Table(title="Processamento Local", show_header=True)
    table3.add_column("Componente", style="cyan")
    table3.add_column("Status", style="white")

    table3.add_row("Estratégia", local_config.EXTRACTION_STRATEGY)
    table3.add_row("Threshold Confiança", f"{local_config.LOCAL_CONFIDENCE_THRESHOLD:.1%}")
    table3.add_row("Marker Enabled", "ON" if local_config.MARKER_ENABLED else "OFF")
    table3.add_row("Surya Enabled", "ON" if local_config.SURYA_ENABLED else "OFF")
    table3.add_row("RAG Enabled", "ON" if local_config.RAG_ENABLED else "OFF")

    console.print(table3)

    # Artigos
    if paths.MAPPING_CSV.exists():
        from src.config import load_mapping, get_pending_articles
        mapping = load_mapping(paths.MAPPING_CSV)
        pending = get_pending_articles(paths.MAPPING_CSV)

        console.print(f"\n[bold]Artigos:[/bold] {len(mapping)} total, {len(pending)} pendentes")


@app.command()
def check():
    """Verifica todas as dependências (torch, marker, surya, ollama)."""
    console.print(Panel.fit("[bold blue]Verificação de Dependências[/bold blue]"))

    checks = []

    # Python
    import platform
    checks.append(("Python", platform.python_version(), True))

    # Torch + CUDA
    try:
        import torch
        cuda = torch.cuda.is_available()
        gpu = torch.cuda.get_device_name(0) if cuda else "N/A"
        checks.append(("PyTorch", f"{torch.__version__} (CUDA: {cuda})", cuda))
        if cuda:
            checks.append(("GPU", gpu, True))
    except ImportError:
        checks.append(("PyTorch", "Não instalado", False))

    # Marker
    try:
        from src.adapters.marker_adapter import get_marker_info
        info = get_marker_info()
        checks.append(("Marker-PDF", f"v{info['version']} (GPU: {info['gpu_available']})", info['available']))
    except Exception as e:
        checks.append(("Marker-PDF", f"Erro: {e}", False))

    # Surya
    try:
        from src.adapters.surya_adapter import get_surya_info
        info = get_surya_info()
        checks.append(("Surya-OCR", f"GPU: {info['gpu_available']}", info['available']))
    except Exception as e:
        checks.append(("Surya-OCR", f"Erro: {e}", False))

    # Ollama
    try:
        from src.adapters.ollama_adapter import test_connection
        status = test_connection()
        if status['available']:
            checks.append(("Ollama", f"{len(status['models'])} modelos", True))
            if status['missing_models']:
                for m in status['missing_models']:
                    checks.append(("  -> Missing", m, False))
        else:
            checks.append(("Ollama", "Não disponível", False))
    except Exception as e:
        checks.append(("Ollama", f"Erro: {e}", False))

    # ChromaDB
    try:
        import chromadb
        checks.append(("ChromaDB", f"v{chromadb.__version__}", True))
    except ImportError:
        checks.append(("ChromaDB", "Não instalado", False))

    # Mostrar resultados
    table = Table(show_header=True)
    table.add_column("Componente", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("OK", style="green")

    for name, status, ok in checks:
        table.add_row(name, status, "[green]OK[/green]" if ok else "[red]NO[/red]")

    console.print(table)

    # Resumo
    ok_count = sum(1 for _, _, ok in checks if ok)
    console.print(f"\n[bold]Resultado:[/bold] {ok_count}/{len(checks)} verificações OK")


@app.command()
def ollama_list():
    """Lista modelos Ollama disponíveis."""
    try:
        from src.adapters.ollama_adapter import list_models, DEFAULT_MODELS

        models = list_models()

        if not models:
            console.print("[yellow]Nenhum modelo encontrado. Ollama está rodando?[/yellow]")
            return

        table = Table(title="Modelos Ollama", show_header=True)
        table.add_column("Nome", style="cyan")
        table.add_column("Tamanho", style="white")
        table.add_column("Família", style="white")
        table.add_column("Uso Recomendado", style="green")

        for model in models:
            # Verificar uso recomendado
            uso = []
            for task, default_model in DEFAULT_MODELS.items():
                if model.name == default_model or model.name.startswith(default_model.split(":")[0]):
                    uso.append(task)

            table.add_row(
                model.name,
                f"{model.size_gb:.1f} GB",
                model.family,
                ", ".join(uso) if uso else "-",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Erro: {e}[/red]")


# ============================================================
# Comandos de Pipeline
# ============================================================

@app.command()
def ingest(
    article: Optional[str] = typer.Option(None, "--article", "-a", help="ID do artigo específico"),
    strategy: str = typer.Option("marker", "--strategy", "-s", help="Estratégia: marker|pymupdf|hybrid"),
    force: bool = typer.Option(False, "--force", "-f", help="Forçar reprocessamento"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simular sem processar"),
):
    """Ingere PDFs (converte para texto/markdown)."""
    from src.config import paths, load_mapping
    from src.context import create_context

    console.print(Panel.fit(f"[bold blue]Ingestão de PDFs[/bold blue] (strategy={strategy})"))

    ctx = create_context()

    if article:
        articles = [a for a in load_mapping(paths.MAPPING_CSV) if a["ArtigoID"] == article]
    else:
        articles = load_mapping(paths.MAPPING_CSV)

    console.print(f"Artigos a processar: {len(articles)}")

    if dry_run:
        console.print("[yellow]Modo dry-run - nenhum processamento será feito[/yellow]")
        return

    # Processar
    from src.pipeline_ingest import run_ingest

    for art in articles:
        artigo_id = art["ArtigoID"]
        console.print(f"\n[cyan]Processando {artigo_id}...[/cyan]")

        try:
            result = run_ingest(
                paths=paths,
                extraction_config=ctx.extraction_config,
                artigo_id=artigo_id,
                force=force,
                logger=ctx.logger,
            )
            console.print(f"  [green]OK[/green]")
        except Exception as e:
            console.print(f"  [red]Erro: {e}[/red]")


@app.command()
def extract(
    article: Optional[str] = typer.Option(None, "--article", "-a", help="ID do artigo específico"),
    strategy: str = typer.Option("local_first", "--strategy", "-s",
                                  help="Estratégia: local_first|api_first|local_only|api_only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simular sem processar"),
):
    """Extrai dados CIMO dos artigos ingeridos."""
    from src.config import paths, load_mapping

    console.print(Panel.fit(f"[bold blue]Extração CIMO[/bold blue] (strategy={strategy})"))

    if article:
        articles = [a for a in load_mapping(paths.MAPPING_CSV) if a["ArtigoID"] == article]
    else:
        articles = load_mapping(paths.MAPPING_CSV)

    console.print(f"Artigos a processar: {len(articles)}")

    if dry_run:
        console.print("[yellow]Modo dry-run - nenhum processamento será feito[/yellow]")
        return

    # Processar com cascata
    from src.pipeline_cascade import extract_cascade

    total_local = 0
    total_api = 0
    total_saved = 0

    for art in articles:
        artigo_id = art["ArtigoID"]
        console.print(f"\n[cyan]Extraindo {artigo_id}...[/cyan]")

        try:
            # Carregar texto
            work_dir = paths.WORK / artigo_id
            texts_file = work_dir / "texts.json"

            if not texts_file.exists():
                console.print(f"  [yellow]Texto não encontrado - execute ingest primeiro[/yellow]")
                continue

            import json
            with open(texts_file) as f:
                texts = json.load(f)

            full_text = "\n\n".join(texts.values())

            # Carregar prompt
            prompt_template = paths.GUIA_PROMPT.read_text(encoding="utf-8")
            prompt_template += "\n\nTexto do artigo:\n{TEXT}"

            # Extrair
            result = extract_cascade(
                artigo_id,
                full_text,
                prompt_template,
                strategy=strategy,
            )

            # Mostrar resultado
            source = result.source.value
            if "local" in source:
                total_local += 1
            else:
                total_api += 1

            total_saved += result.tokens_saved

            console.print(f"  Source: {source}")
            console.print(f"  Confidence: {result.confidence:.2f}")
            console.print(f"  Tokens local: {result.metrics.local_tokens}")
            if result.metrics.api_tokens:
                console.print(f"  Tokens API: {result.metrics.api_tokens}")
                console.print(f"  Custo estimado: ${result.metrics.api_cost_estimate:.4f}")

            # Salvar YAML
            if result.success and result.yaml_content:
                yaml_path = paths.YAMLS / f"{artigo_id}.yaml"
                yaml_path.write_text(result.yaml_content, encoding="utf-8")
                console.print(f"  [green]Salvo em {yaml_path.name}[/green]")

        except Exception as e:
            console.print(f"  [red]Erro: {e}[/red]")

    # Resumo
    console.print(f"\n[bold]Resumo:[/bold]")
    console.print(f"  Extrações locais: {total_local}")
    console.print(f"  Extrações API: {total_api}")
    console.print(f"  Tokens economizados: ~{total_saved:,}")


@app.command()
def validate(
    article: Optional[str] = typer.Option(None, "--article", "-a", help="ID do artigo específico"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Arquivo de relatório"),
):
    """Valida YAMLs extraídos contra schema e regras."""
    from src.config import paths
    from src.validators import validate_extraction

    console.print(Panel.fit("[bold blue]Validação de YAMLs[/bold blue]"))

    if article:
        yaml_files = [paths.YAMLS / f"{article}.yaml"]
    else:
        yaml_files = list(paths.YAMLS.glob("*.yaml"))

    console.print(f"Arquivos a validar: {len(yaml_files)}")

    results = []
    valid_count = 0

    for yaml_path in yaml_files:
        if not yaml_path.exists():
            continue

        artigo_id = yaml_path.stem
        yaml_content = yaml_path.read_text(encoding="utf-8")

        try:
            result = validate_extraction(yaml_content, artigo_id)

            status = "[green]VÁLIDO[/green]" if result.is_valid else "[red]INVÁLIDO[/red]"
            console.print(f"{artigo_id}: {status} ({len(result.errors)} erros, {len(result.warnings)} warnings)")

            if result.is_valid:
                valid_count += 1

            results.append({
                "artigo_id": artigo_id,
                "valid": result.is_valid,
                "errors": len(result.errors),
                "warnings": len(result.warnings),
            })

        except Exception as e:
            console.print(f"{artigo_id}: [red]ERRO - {e}[/red]")
            results.append({
                "artigo_id": artigo_id,
                "valid": False,
                "errors": 1,
                "warnings": 0,
                "error": str(e),
            })

    console.print(f"\n[bold]Resultado:[/bold] {valid_count}/{len(yaml_files)} válidos")

    if output:
        import json
        Path(output).write_text(json.dumps(results, indent=2), encoding="utf-8")
        console.print(f"Relatório salvo em {output}")


@app.command()
def consolidate(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Arquivo Excel de saída"),
):
    """Consolida YAMLs em arquivo Excel."""
    from src.config import paths
    from src.consolidate import consolidate_yamls

    console.print(Panel.fit("[bold blue]Consolidação[/bold blue]"))

    output_path = Path(output) if output else paths.CONSOLIDATED / "SAEC_Consolidated.xlsx"

    try:
        result = consolidate_yamls(
            yamls_dir=paths.YAMLS,
            output_path=output_path,
        )

        console.print(f"[green]Consolidação concluída![/green]")
        console.print(f"  Artigos: {result.get('total_articles', 0)}")
        console.print(f"  Arquivo: {output_path}")

    except Exception as e:
        console.print(f"[red]Erro: {e}[/red]")


@app.command()
def run(
    article: Optional[str] = typer.Option(None, "--article", "-a", help="ID do artigo específico"),
    strategy: str = typer.Option("local_first", "--strategy", "-s", help="Estratégia de extração"),
    skip_ingest: bool = typer.Option(False, "--skip-ingest", help="Pular ingestão"),
    skip_extract: bool = typer.Option(False, "--skip-extract", help="Pular extração"),
    skip_validate: bool = typer.Option(False, "--skip-validate", help="Pular validação"),
    skip_consolidate: bool = typer.Option(False, "--skip-consolidate", help="Pular consolidação"),
):
    """Executa pipeline completo (ingest -> extract -> validate -> consolidate)."""
    console.print(Panel.fit("[bold blue]Pipeline Completo SAEC-O&G[/bold blue]"))

    steps = []
    if not skip_ingest:
        steps.append(("Ingestão", lambda: ingest(article=article, strategy="marker")))
    if not skip_extract:
        steps.append(("Extração", lambda: extract(article=article, strategy=strategy)))
    if not skip_validate:
        steps.append(("Validação", lambda: validate(article=article)))
    if not skip_consolidate:
        steps.append(("Consolidação", lambda: consolidate()))

    for i, (name, func) in enumerate(steps, 1):
        console.print(f"\n[bold]=== Etapa {i}/{len(steps)}: {name} ===[/bold]")
        try:
            func()
        except Exception as e:
            console.print(f"[red]Erro na etapa {name}: {e}[/red]")
            if not typer.confirm("Continuar mesmo assim?"):
                raise typer.Abort()


# ============================================================
# Comandos RAG
# ============================================================

@app.command()
def rag_index(
    article: Optional[str] = typer.Option(None, "--article", "-a", help="Indexar artigo específico"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Reconstruir índice completo"),
):
    """Constrói/atualiza índice RAG para busca semântica."""
    from src.config import paths
    from src.adapters.rag_store import RAGStore, RAGConfig

    console.print(Panel.fit("[bold blue]Indexação RAG[/bold blue]"))

    # Configurar store
    rag_dir = paths.OUTPUTS / "rag_index"
    config = RAGConfig(persist_dir=rag_dir)
    store = RAGStore(config)

    if rebuild:
        console.print("[yellow]Reconstruindo índice completo...[/yellow]")
        # Limpar índice existente
        import shutil
        if rag_dir.exists():
            shutil.rmtree(rag_dir)

    # Listar artigos para indexar
    if article:
        artigos = [article]
    else:
        artigos = [p.stem for p in paths.YAMLS.glob("*.yaml")]

    console.print(f"Artigos a indexar: {len(artigos)}")

    total_chunks = 0
    for artigo_id in artigos:
        # Carregar texto
        texts_file = paths.WORK / artigo_id / "texts.json"
        if not texts_file.exists():
            console.print(f"  {artigo_id}: [yellow]sem texto[/yellow]")
            continue

        import json
        with open(texts_file) as f:
            texts = json.load(f)

        full_text = "\n\n".join(texts.values())

        # Indexar
        try:
            n_chunks = store.add_article(artigo_id, full_text)
            total_chunks += n_chunks
            console.print(f"  {artigo_id}: {n_chunks} chunks")
        except Exception as e:
            console.print(f"  {artigo_id}: [red]erro - {e}[/red]")

    console.print(f"\n[bold]Total:[/bold] {total_chunks} chunks indexados")


@app.command()
def rag_search(
    query: str = typer.Argument(..., help="Query de busca"),
    article: Optional[str] = typer.Option(None, "--article", "-a", help="Buscar em artigo específico"),
    top_k: int = typer.Option(5, "--top", "-k", help="Número de resultados"),
):
    """Busca semântica no índice RAG."""
    from src.config import paths
    from src.adapters.rag_store import RAGStore, RAGConfig

    rag_dir = paths.OUTPUTS / "rag_index"
    if not rag_dir.exists():
        console.print("[red]Índice RAG não encontrado. Execute 'saec rag-index' primeiro.[/red]")
        raise typer.Exit(1)

    config = RAGConfig(persist_dir=rag_dir)
    store = RAGStore(config)

    results = store.search(query, artigo_id=article, top_k=top_k)

    if not results:
        console.print("[yellow]Nenhum resultado encontrado.[/yellow]")
        return

    console.print(f"\n[bold]Resultados para:[/bold] {query}\n")

    for i, result in enumerate(results, 1):
        console.print(f"[cyan]{i}. {result.chunk.artigo_id}[/cyan] (score: {result.score:.3f})")
        if result.chunk.section:
            console.print(f"   Seção: {result.chunk.section}")
        console.print(f"   {result.chunk.text[:200]}...")
        console.print()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    app()
