"""Pipeline step: PDF ingestion."""

from __future__ import annotations

import json
from pathlib import Path
import logging
from typing import Optional

try:
    from .config import load_mapping
    from .pdf_vision import get_pdf_info, check_pdf_quality, analyze_pdf_pages, extract_hybrid
except Exception:  # pragma: no cover - standalone usage
    from config import load_mapping
    from pdf_vision import get_pdf_info, check_pdf_quality, analyze_pdf_pages, extract_hybrid


def _save_ingest_outputs(
    *,
    work_dir: Path,
    hybrid_meta: dict,
    texts_data: dict,
    hybrid_file: Path,
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with open(hybrid_file, "w", encoding="utf-8") as f:
        json.dump(hybrid_meta, f, indent=2, ensure_ascii=False)
    with open(work_dir / "texts.json", "w", encoding="utf-8") as f:
        json.dump(texts_data, f, indent=2, ensure_ascii=False)


def run_ingest(
    *,
    paths,
    extraction_config,
    artigo_id: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> dict:
    log = logger or logging.getLogger("saec")
    mapping = load_mapping(paths.MAPPING_CSV)

    ingested = []
    pending = []
    for article in mapping:
        aid = article["ArtigoID"]
        hybrid_file = paths.WORK / aid / "hybrid.json"
        if hybrid_file.exists():
            ingested.append(article)
        else:
            pending.append(article)

    if artigo_id:
        article = next((a for a in mapping if a["ArtigoID"] == artigo_id), None)
        if not article:
            raise IngestError(f"Artigo {artigo_id} não encontrado no mapping")
        articles_to_process = [article]
    else:
        articles_to_process = pending

    results = {"success": 0, "cached": 0, "error": 0, "total": len(articles_to_process)}

    if dry_run:
        return results

    for article in articles_to_process:
        aid = article["ArtigoID"]
        arquivo = article["Arquivo"]

        pdf_path = paths.ARTICLES / arquivo
        work_dir = paths.WORK / aid
        pages_dir = work_dir / "pages"
        hybrid_file = work_dir / "hybrid.json"

        if not force and hybrid_file.exists():
            results["cached"] += 1
            continue

        if not pdf_path.exists():
            results["error"] += 1
            continue

        try:
            info = get_pdf_info(pdf_path)
            _ = check_pdf_quality(pdf_path)
            _ = analyze_pdf_pages(pdf_path)
            result = extract_hybrid(pdf_path, pages_dir, dpi=extraction_config.IMAGE_DPI)

            hybrid_meta = {
                "artigo_id": aid,
                "arquivo": arquivo,
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

            texts_data = {p["page_num"]: p["content"] for p in result["pages"] if p["type"] == "text"}
            _save_ingest_outputs(
                work_dir=work_dir,
                hybrid_meta=hybrid_meta,
                texts_data=texts_data,
                hybrid_file=hybrid_file,
            )
            results["success"] += 1

        except Exception as e:
            results["error"] += 1
            log.warning(
                "Falha na ingestao",
                extra={"artigo_id": aid, "provider": "-", "action": "ingest"},
            )
            continue

    return results
