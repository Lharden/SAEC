"""Pipeline step: LLM extraction."""

from __future__ import annotations

import json
from pathlib import Path
import logging
from typing import Optional

try:
    from .config import load_mapping
    from .processors import ArticleProcessor
except Exception:  # pragma: no cover - standalone usage
    from config import load_mapping
    from processors import ArticleProcessor


def _load_hybrid_json(work_dir: Path) -> dict:
    with open(work_dir / "hybrid.json", "r", encoding="utf-8") as f:
        return json.load(f)


def run_extract(
    *,
    paths,
    client,
    guia_path: Path,
    output_dir: Path,
    artigo_id: Optional[str] = None,
    dry_run: bool = False,
    logger: logging.Logger | None = None,
) -> dict:
    log = logger or logging.getLogger("saec")
    mapping = load_mapping(paths.MAPPING_CSV)

    ready = []
    for article in mapping:
        aid = article["ArtigoID"]
        hybrid_file = paths.WORK / aid / "hybrid.json"
        yaml_file = paths.YAMLS / f"{aid}.yaml"
        if hybrid_file.exists() and not yaml_file.exists():
            ready.append(article)

    if artigo_id:
        article = next((a for a in ready if a["ArtigoID"] == artigo_id), None)
        if not article:
            raise ValueError(f"Artigo {artigo_id} não encontrado ou já processado")
        articles_to_process = [article]
    else:
        articles_to_process = ready

    results = {"success": 0, "error": 0, "skipped": 0, "total": len(articles_to_process)}

    if dry_run:
        return results

    processor = ArticleProcessor(
        client=client,
        guia_path=guia_path,
        output_dir=output_dir,
        work_dir=paths.WORK,
    )

    for article in articles_to_process:
        aid = article["ArtigoID"]
        try:
            work_dir = paths.WORK / aid
            hybrid = _load_hybrid_json(work_dir)
            yaml_content, _ = processor.process_article(
                artigo_id=aid,
                hybrid_meta=hybrid,
                work_dir=work_dir,
            )

            yaml_path = paths.YAMLS / f"{aid}.yaml"
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            results["success"] += 1

        except Exception:
            results["error"] += 1
            log.warning(
                "Falha na extracao",
                extra={"artigo_id": aid, "provider": "-", "action": "extract"},
            )
            continue

    return results
