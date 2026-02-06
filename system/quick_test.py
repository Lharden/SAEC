#!/usr/bin/env python3
"""
Quick test - Ingere um PDF e roda benchmark.
Uso: python quick_test.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import paths, extraction_config, llm_config, local_config
from context import make_context
from pdf_vision import extract_hybrid, get_pdf_info
from processors import ArticleProcessor
from llm_client import LLMClient


def ingest_pdf(pdf_path: Path, artigo_id: str) -> dict:
    """Ingere um PDF e retorna metadados."""
    work_dir = paths.EXTRACTION / "outputs" / artigo_id
    pages_dir = work_dir / "pages"
    hybrid_file = work_dir / "hybrid.json"

    # Se ja existe, retornar
    if hybrid_file.exists():
        print(f"[CACHE] Artigo {artigo_id} ja ingerido")
        with open(hybrid_file, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[INGEST] Processando {pdf_path.name}...")
    start = time.time()

    # Extrair
    info = get_pdf_info(pdf_path)
    result = extract_hybrid(pdf_path, pages_dir, dpi=extraction_config.IMAGE_DPI)

    # Montar metadados
    hybrid_meta = {
        "artigo_id": artigo_id,
        "arquivo": pdf_path.name,
        "analysis": result["analysis"],
        "stats": result["stats"],
        "pages_info": [
            {
                "page_num": p["page_num"],
                "type": p["type"],
                "path": str(p["path"]) if p["type"] == "image" else None,
            }
            for p in result["pages"]
        ],
        "info": info,
    }

    # Salvar
    work_dir.mkdir(parents=True, exist_ok=True)
    with open(hybrid_file, "w", encoding="utf-8") as f:
        json.dump(hybrid_meta, f, indent=2, ensure_ascii=False)

    texts_data = {str(p["page_num"]): p["content"] for p in result["pages"] if p["type"] == "text"}
    with open(work_dir / "texts.json", "w", encoding="utf-8") as f:
        json.dump(texts_data, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - start
    print(f"[INGEST] Concluido em {elapsed:.1f}s - {len(result['pages'])} paginas")

    return hybrid_meta


def run_extraction(artigo_id: str, hybrid_meta: dict) -> tuple[str, object]:
    """Executa extracao CIMO."""
    work_dir = paths.EXTRACTION / "outputs" / artigo_id

    print(f"\n[EXTRACT] Iniciando extracao CIMO...")
    print(f"  RAG: {local_config.RAG_ENABLED}")
    print(f"  Cascade: {local_config.USE_CASCADE}")
    print(f"  Strategy: {local_config.EXTRACTION_STRATEGY}")

    start = time.time()

    # Criar contexto e cliente
    ctx = make_context()
    client = LLMClient(ctx)

    # Criar processor
    processor = ArticleProcessor(
        client=client,
        guia_path=paths.GUIA_PROMPT,  # system/prompts/guia_v3_3_prompt.md
        output_dir=paths.EXTRACTION / "outputs" / "yamls",
        work_dir=paths.EXTRACTION / "outputs",
    )

    # Executar
    yaml_content, validation = processor.process_article(
        artigo_id=artigo_id,
        hybrid_meta=hybrid_meta,
        work_dir=work_dir,
    )

    elapsed = time.time() - start

    print(f"\n[EXTRACT] Concluido em {elapsed:.1f}s")
    print(f"  Valido: {validation.is_valid}")
    print(f"  Erros: {len(validation.errors)}")
    print(f"  Warnings: {len(validation.warnings)}")

    if validation.errors:
        print("\n  Erros encontrados:")
        for e in validation.errors[:5]:
            print(f"    - {e[:80]}...")

    return yaml_content, validation


def main():
    # PDF para teste
    pdf_name = "Leveraging AI for Inventory Management and Accurate Forecast-An Industrial Field Study.pdf"
    pdf_path = paths.PROJECT_ROOT / "02 T2" / pdf_name
    artigo_id = "ART_TEST_001"

    if not pdf_path.exists():
        print(f"[ERRO] PDF nao encontrado: {pdf_path}")
        # Listar PDFs disponiveis
        t2_dir = paths.PROJECT_ROOT / "02 T2"
        if t2_dir.exists():
            pdfs = list(t2_dir.glob("*.pdf"))
            print(f"\nPDFs disponiveis ({len(pdfs)}):")
            for p in pdfs[:5]:
                print(f"  - {p.name}")
        return

    print("="*70)
    print("SAEC-O&G - Quick Test")
    print("="*70)
    print(f"PDF: {pdf_name}")
    print(f"Artigo ID: {artigo_id}")
    print("="*70)

    # Etapa 1: Ingestao
    hybrid_meta = ingest_pdf(pdf_path, artigo_id)

    # Etapa 2: Extracao
    yaml_content, validation = run_extraction(artigo_id, hybrid_meta)

    # Resultado
    print("\n" + "="*70)
    print("RESULTADO FINAL")
    print("="*70)
    print(f"Validacao: {'APROVADO' if validation.is_valid else 'REPROVADO'}")

    # Salvar YAML
    yaml_path = paths.EXTRACTION / "outputs" / "yamls" / f"{artigo_id}.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"YAML salvo: {yaml_path}")

    # Mostrar preview
    print("\nPreview do YAML (primeiras 30 linhas):")
    print("-"*50)
    for i, line in enumerate(yaml_content.split("\n")[:30], 1):
        print(f"{i:3}: {line}")


if __name__ == "__main__":
    main()
