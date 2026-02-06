#!/usr/bin/env python3
"""
Benchmark curto: compara RAG OFF vs RAG ON para um artigo.

Uso:
  .\.venv\Scripts\python system\benchmark_short.py --artigo ART_002
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.context import make_context
from src.config import local_config, paths
from src.llm_client import LLMClient
from src.processors import ArticleProcessor


def load_hybrid(artigo_id: str) -> dict:
    work_dir = paths.WORK / artigo_id
    hybrid_path = work_dir / "hybrid.json"
    return json.loads(hybrid_path.read_text(encoding="utf-8"))


def run_once(artigo_id: str, rag_enabled: bool) -> dict:
    local_config.RAG_ENABLED = rag_enabled

    ctx = make_context()
    client = LLMClient(ctx)
    client.reset_usage()

    processor = ArticleProcessor(
        client=client,
        guia_path=paths.GUIA_PROMPT,
        output_dir=paths.YAMLS,
        work_dir=paths.WORK,
    )

    work_dir = paths.WORK / artigo_id
    hybrid = load_hybrid(artigo_id)

    start = time.time()
    yaml_content, result = processor.process_article(
        artigo_id=artigo_id,
        hybrid_meta=hybrid,
        work_dir=work_dir,
    )
    elapsed = time.time() - start

    usage = client.get_usage_totals()
    return {
        "rag_enabled": rag_enabled,
        "elapsed_s": round(elapsed, 2),
        "yaml_chars": len(yaml_content or ""),
        "valid": bool(result.is_valid),
        "usage": usage,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artigo", required=True)
    args = parser.parse_args()

    artigo_id = args.artigo.strip()
    if not (paths.WORK / artigo_id / "hybrid.json").exists():
        raise FileNotFoundError(f"hybrid.json nao encontrado para {artigo_id}")

    print(f"[INFO] Benchmark curto para {artigo_id}")

    print("[INFO] Rodando baseline (RAG OFF)...")
    baseline = run_once(artigo_id, rag_enabled=False)

    print("[INFO] Rodando otimizado (RAG ON)...")
    optimized = run_once(artigo_id, rag_enabled=True)

    def _fmt(u: dict) -> str:
        return f"in={u.get('tokens_in',0)} out={u.get('tokens_out',0)} cached={u.get('cached_tokens',0)}"

    print("\n=== RESULTADO ===")
    print(f"Baseline  | time={baseline['elapsed_s']}s | valid={baseline['valid']} | usage=({_fmt(baseline['usage'])})")
    print(f"Otimizado | time={optimized['elapsed_s']}s | valid={optimized['valid']} | usage=({_fmt(optimized['usage'])})")

    if baseline["valid"] and optimized["valid"]:
        in_b = baseline["usage"].get("tokens_in", 0)
        in_o = optimized["usage"].get("tokens_in", 0)
        if in_b:
            saved = 100.0 * (in_b - in_o) / max(in_b, 1)
            print(f"[OK] Economia de tokens_in: {saved:.1f}%")


if __name__ == "__main__":
    main()
