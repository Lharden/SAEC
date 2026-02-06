#!/usr/bin/env python3
"""
Benchmark de Economia de Tokens - SAEC-O&G

Compara processamento com e sem otimizacoes (RAG + Cascade).
Mede: tokens, tempo, qualidade.

Uso:
    python benchmark.py --artigo ART_001
    python benchmark.py --artigo ART_001 --compare  # Compara com/sem otimizacoes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import paths, llm_config, local_config, extraction_config
from context import make_context
from processors import ArticleProcessor
from llm_client import LLMClient


@dataclass
class BenchmarkResult:
    """Resultado de um benchmark."""
    artigo_id: str
    mode: str  # "optimized" ou "baseline"

    # Tempo
    start_time: float = 0.0
    end_time: float = 0.0
    duration_seconds: float = 0.0

    # Tokens (estimado)
    input_tokens_estimate: int = 0
    output_tokens_estimate: int = 0

    # Qualidade
    is_valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Fonte
    extraction_source: str = ""  # "local_ollama", "api_anthropic", etc.
    rag_used: bool = False
    cascade_used: bool = False

    # Custo estimado (USD)
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "artigo_id": self.artigo_id,
            "mode": self.mode,
            "duration_seconds": round(self.duration_seconds, 2),
            "input_tokens_estimate": self.input_tokens_estimate,
            "output_tokens_estimate": self.output_tokens_estimate,
            "is_valid": self.is_valid,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "extraction_source": self.extraction_source,
            "rag_used": self.rag_used,
            "cascade_used": self.cascade_used,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
        }


def estimate_tokens(text: str) -> int:
    """Estima tokens (aprox 4 chars por token)."""
    return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, provider: str) -> float:
    """Estima custo em USD baseado no provider."""
    # Precos aproximados por 1M tokens (2024)
    prices = {
        "anthropic": {"input": 3.0, "output": 15.0},  # Claude 3.5 Sonnet
        "openai": {"input": 2.5, "output": 10.0},      # GPT-4o
        "ollama": {"input": 0.0, "output": 0.0},       # Local = gratis
    }

    p = prices.get(provider, prices["anthropic"])
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def run_benchmark(
    artigo_id: str,
    *,
    use_optimizations: bool = True,
) -> BenchmarkResult:
    """
    Executa benchmark para um artigo.

    Args:
        artigo_id: ID do artigo
        use_optimizations: Se True, usa RAG + Cascade. Se False, modo baseline.
    """
    mode = "optimized" if use_optimizations else "baseline"
    result = BenchmarkResult(artigo_id=artigo_id, mode=mode)

    # Configurar ambiente
    if use_optimizations:
        os.environ["RAG_ENABLED"] = "true"
        os.environ["USE_CASCADE"] = str(local_config.USE_CASCADE).lower()
        result.rag_used = True
        result.cascade_used = local_config.USE_CASCADE
    else:
        os.environ["RAG_ENABLED"] = "false"
        os.environ["USE_CASCADE"] = "false"
        result.rag_used = False
        result.cascade_used = False

    # Recarregar config
    from importlib import reload
    import config
    reload(config)

    # Preparar paths
    work_dir = paths.EXTRACTION / "outputs" / artigo_id
    hybrid_path = work_dir / "hybrid.json"

    if not hybrid_path.exists():
        print(f"[ERRO] Artigo {artigo_id} nao encontrado em {work_dir}")
        print("       Execute primeiro: python -m pipeline_ingest --artigo <ID>")
        return result

    # Carregar metadados
    with open(hybrid_path, "r", encoding="utf-8") as f:
        hybrid_meta = json.load(f)

    # Estimar input tokens
    texts_path = work_dir / "texts.json"
    if texts_path.exists():
        with open(texts_path, "r", encoding="utf-8") as f:
            texts = json.load(f)
        full_text = "\n".join(texts.values())
        result.input_tokens_estimate = estimate_tokens(full_text)

    # Criar contexto e cliente
    ctx = make_context()
    client = LLMClient(ctx)

    # Criar processor
    processor = ArticleProcessor(
        client=client,
        guia_path=paths.EXTRACTION / "prompts" / "guia_v3_3_prompt.md",
        output_dir=paths.EXTRACTION / "outputs" / "yamls",
        work_dir=paths.EXTRACTION / "outputs",
    )

    # Executar
    print(f"\n{'='*60}")
    print(f"Benchmark: {artigo_id} [{mode.upper()}]")
    print(f"RAG: {result.rag_used} | Cascade: {result.cascade_used}")
    print(f"{'='*60}")

    result.start_time = time.time()

    try:
        yaml_content, validation = processor.process_article(
            artigo_id=artigo_id,
            hybrid_meta=hybrid_meta,
            work_dir=work_dir,
        )

        result.is_valid = validation.is_valid
        result.errors = validation.errors
        result.warnings = validation.warnings
        result.output_tokens_estimate = estimate_tokens(yaml_content)

        # Detectar fonte
        if result.cascade_used and "local" in str(local_config.EXTRACTION_STRATEGY):
            result.extraction_source = "local_ollama"
        else:
            result.extraction_source = f"api_{llm_config.PRIMARY_PROVIDER}"

    except Exception as e:
        result.errors = [str(e)]
        result.extraction_source = "error"

    result.end_time = time.time()
    result.duration_seconds = result.end_time - result.start_time

    # Estimar custo
    provider = "ollama" if "local" in result.extraction_source else llm_config.PRIMARY_PROVIDER
    result.estimated_cost_usd = estimate_cost(
        result.input_tokens_estimate,
        result.output_tokens_estimate,
        provider,
    )

    return result


def compare_modes(artigo_id: str) -> dict:
    """Compara modo otimizado vs baseline."""
    print("\n" + "="*70)
    print("BENCHMARK COMPARATIVO")
    print("="*70)

    # Baseline (sem otimizacoes)
    print("\n[1/2] Executando BASELINE (sem RAG/Cascade)...")
    baseline = run_benchmark(artigo_id, use_optimizations=False)

    # Otimizado
    print("\n[2/2] Executando OTIMIZADO (com RAG/Cascade)...")
    optimized = run_benchmark(artigo_id, use_optimizations=True)

    # Calcular economia
    time_diff = baseline.duration_seconds - optimized.duration_seconds
    cost_diff = baseline.estimated_cost_usd - optimized.estimated_cost_usd
    cost_pct = (cost_diff / baseline.estimated_cost_usd * 100) if baseline.estimated_cost_usd > 0 else 0

    comparison = {
        "artigo_id": artigo_id,
        "timestamp": datetime.now().isoformat(),
        "baseline": baseline.to_dict(),
        "optimized": optimized.to_dict(),
        "savings": {
            "time_seconds": round(time_diff, 2),
            "cost_usd": round(cost_diff, 4),
            "cost_percent": round(cost_pct, 1),
        },
        "quality_preserved": baseline.is_valid == optimized.is_valid,
    }

    # Imprimir resumo
    print("\n" + "="*70)
    print("RESULTADO COMPARATIVO")
    print("="*70)
    print(f"\n{'Metrica':<25} {'Baseline':<20} {'Otimizado':<20} {'Economia':<15}")
    print("-"*80)
    print(f"{'Tempo (s)':<25} {baseline.duration_seconds:<20.1f} {optimized.duration_seconds:<20.1f} {time_diff:>+.1f}s")
    print(f"{'Custo estimado (USD)':<25} ${baseline.estimated_cost_usd:<19.4f} ${optimized.estimated_cost_usd:<19.4f} {cost_pct:>+.1f}%")
    print(f"{'Input tokens':<25} {baseline.input_tokens_estimate:<20,} {optimized.input_tokens_estimate:<20,}")
    print(f"{'Validacao OK':<25} {str(baseline.is_valid):<20} {str(optimized.is_valid):<20}")
    print(f"{'Fonte':<25} {baseline.extraction_source:<20} {optimized.extraction_source:<20}")
    print("-"*80)

    if comparison["quality_preserved"]:
        print("\n[OK] Qualidade preservada!")
    else:
        print("\n[ATENCAO] Diferenca na validacao - verificar manualmente.")

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Benchmark de economia SAEC-O&G")
    parser.add_argument("--artigo", "-a", required=True, help="ID do artigo (ex: ART_001)")
    parser.add_argument("--compare", "-c", action="store_true", help="Comparar modos otimizado vs baseline")
    parser.add_argument("--output", "-o", help="Arquivo JSON para salvar resultado")

    args = parser.parse_args()

    if args.compare:
        result = compare_modes(args.artigo)
    else:
        bench = run_benchmark(args.artigo, use_optimizations=True)
        result = bench.to_dict()

        print("\n" + "="*60)
        print("RESULTADO")
        print("="*60)
        for k, v in result.items():
            print(f"  {k}: {v}")

    # Salvar se solicitado
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nResultado salvo em: {output_path}")

    return result


if __name__ == "__main__":
    main()
