"""qa_guideline.py

Guia v3.3 – Auditoria de Qualidade (QA) pós-validação de schema.

Por que existe?
--------------
O validador de YAML garante *conformidade estrutural* (schema + regras R*), mas não garante
que o conteúdo esteja bem ancorado no artigo ou preenchido com qualidade.

Este módulo adiciona uma segunda camada de QA baseada em:
- Rastreabilidade das Quotes no texto extraído do PDF (outputs/work/<ART>/texts.json)
- Heurísticas de completude (NR em campos críticos)
- Sinais de baixa qualidade (quotes placeholder, páginas NR etc.)

Uso típico (notebooks)
---------------------
from qa_guideline import run_qa
qa_df, report_path = run_qa(threshold=80)

Requisitos
----------
- PyYAML
- rapidfuzz
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml
from rapidfuzz import fuzz


def _load_profile_engine():
    try:
        if __package__:
            return __import__(f"{__package__}.profile_engine", fromlist=["dummy"])
        return __import__("profile_engine", fromlist=["dummy"])
    except (ImportError, ModuleNotFoundError):
        return None


_profile_engine = _load_profile_engine()

def _load_paths():
    try:
        from .config import paths as cfg_paths
    except ImportError:  # pragma: no cover - standalone usage
        from config import paths as cfg_paths
    return cfg_paths


paths = _load_paths()


# ------------------------
# Helpers
# ------------------------

_PLACEHOLDER_PATTERNS = [
    r"^nr$",
    r"^sem informa(ç|c)ão\.?$",
    r"^n/?a$",
]


def _norm_text(s: Any) -> str:
    if s is None:
        return ""
    text = str(s)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _is_placeholder_quote(trecho: str) -> bool:
    t = _norm_text(trecho)
    if len(t) < 10:
        return True
    return any(re.match(p, t) for p in _PLACEHOLDER_PATTERNS)


def _load_texts_json(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if v is None:
                continue
            out[str(k)] = str(v)
    return out


def _best_match_in_pages(needle: str, pages: Dict[str, str]) -> Tuple[float, Optional[str]]:
    needle_n = _norm_text(needle)
    if not needle_n or _is_placeholder_quote(needle_n):
        return 0.0, None

    best = 0.0
    best_page: Optional[str] = None
    for page_id, text in pages.items():
        hay = _norm_text(text)
        if not hay:
            continue
        s = float(fuzz.partial_ratio(needle_n, hay))
        if s > best:
            best = s
            best_page = page_id
    return best, best_page


@dataclass
class QuoteAudit:
    idx: int
    score: float
    matched_page: Optional[str]
    placeholder: bool
    page_field: str


def audit_yaml_file(yaml_path: Path, threshold: float = 80.0) -> Dict[str, Any]:
    doc = list(yaml.safe_load_all(yaml_path.read_text(encoding="utf-8")))[0]
    art_id = str(doc.get("ArtigoID", yaml_path.stem))

    texts_path = paths.WORK / art_id / "texts.json"
    pages: Dict[str, str] = _load_texts_json(texts_path) if texts_path.exists() else {}

    quotes = doc.get("Quotes") or []
    if not isinstance(quotes, list):
        quotes = []

    qa_quotes: List[QuoteAudit] = []
    for i, q in enumerate(quotes):
        if not isinstance(q, dict):
            continue
        trecho = str(q.get("Trecho", ""))
        placeholder = _is_placeholder_quote(trecho)
        score, matched_page = (0.0, None)
        if pages and not placeholder:
            score, matched_page = _best_match_in_pages(trecho, pages)
        qa_quotes.append(
            QuoteAudit(
                idx=i,
                score=score,
                matched_page=matched_page,
                placeholder=placeholder,
                page_field=str(q.get("Página", "")),
            )
        )

    total_q = len(qa_quotes)
    placeholder_q = sum(1 for q in qa_quotes if q.placeholder)
    nr_page_q = sum(1 for q in qa_quotes if "nr" in _norm_text(q.page_field))
    page_nr_ratio = (nr_page_q / total_q) if total_q else 0.0

    matched_q = sum(1 for q in qa_quotes if q.score >= threshold)
    match_rate = (matched_q / total_q) if total_q else 0.0

    # Campos críticos (perfil ativo ou fallback Guia v3.3)
    critical_fields = _resolve_runtime_critical_fields()
    if not critical_fields:
        critical_fields = [
            "SegmentoSetorial",
            "ProcessoSCM_Alvo",
            "TipoRisco_SCRM",
            "ObjetoCrítico",
            "ClasseIA",
            "TarefaAnalítica",
            "FamíliaModelo",
            "TipoDado",
            "CategoriaMecanismo",
            "Mecanismo_Estruturado",
            "Resultados_Quant",
            "Limitações_Artigo",
            "NívelEvidência",
        ]
    nr_critical = 0
    for k in critical_fields:
        v = _norm_text(doc.get(k, ""))
        if not v or v == "nr":
            nr_critical += 1
    nr_ratio = nr_critical / max(1, len(critical_fields))

    # Heurística do guia (já vimos acontecer): Produção com evidência NR
    r3_flag = (
        str(doc.get("Maturidade", "")).strip() == "Produção"
        and str(doc.get("NívelEvidência", "")).strip() == "NR"
    )

    # Status e motivos
    status = "OK"
    reasons: List[str] = []

    # Placeholder sempre pede revisão (ou falha se todas as quotes forem placeholders)
    if total_q and placeholder_q:
        status = "REVIEW"
        reasons.append(f"{placeholder_q}/{total_q} quotes placeholder")

    # Páginas ausentes: em alguns PDFs o número de página não vem explícito,
    # mas ainda assim queremos uma localização consistente (usamos p.<id do texts.json>).
    # Se muitas quotes estão com p.NR, marcamos como REVIEW (não FAIL).
    if total_q and page_nr_ratio >= 0.5:
        if status != "FAIL":
            status = "REVIEW"
        reasons.append(f"pages missing (p.NR) ratio {page_nr_ratio:.2f}")

    # Se temos texts.json, exigimos rastreabilidade mínima
    if pages and total_q:
        if match_rate < 0.5:
            status = "FAIL"
            reasons.append(f"quote match_rate {match_rate:.2f} < 0.50")
        elif match_rate < 0.8 and status != "FAIL":
            status = "REVIEW"
            reasons.append(f"quote match_rate {match_rate:.2f} < 0.80")

    if nr_ratio >= 0.35 and status != "FAIL":
        status = "REVIEW"
        reasons.append(f"NR critical ratio {nr_ratio:.2f}")

    if r3_flag:
        status = "FAIL"
        reasons.append("R3: Produção com NívelEvidência=NR")

    worst_quotes = sorted(qa_quotes, key=lambda q: q.score)[:3]
    worst_str = ", ".join(
        [f"q{w.idx+1}:{w.score:.0f}%" + ("(placeholder)" if w.placeholder else "") for w in worst_quotes]
    )

    return {
        "ArtigoID": art_id,
        "status": status,
        "reasons": " | ".join(reasons),
        "quotes_total": total_q,
        "quotes_placeholder": placeholder_q,
        "quotes_page_nr": nr_page_q,
        "page_nr_ratio": round(page_nr_ratio, 2),
        "quotes_matched": matched_q,
        "quotes_match_rate": round(match_rate, 2),
        "nr_critical_ratio": round(nr_ratio, 2),
        "worst_quotes": worst_str,
        "has_texts_json": bool(pages),
        "threshold": threshold,
        "yaml_path": str(yaml_path),
    }


def _resolve_runtime_critical_fields() -> List[str]:
    if _profile_engine is None:
        return []
    try:
        project_root = _profile_engine.resolve_runtime_project_root()
    except Exception:
        return []
    if project_root is None:
        return []
    try:
        spec, _ref = _profile_engine.load_active_profile_spec(project_root)
    except Exception:
        return []
    fields: List[str] = []
    for field in spec.fields:
        # Prefer mandatory contextual and outcome-like fields.
        if field.required and field.section in {"context", "intervention", "mechanism", "outcome"}:
            fields.append(field.field_id)
    return fields[:20]


def run_qa(threshold: float = 80.0, export: bool = True) -> Tuple[pd.DataFrame, Optional[Path]]:
    rows: List[Dict[str, Any]] = []
    for yp in sorted(paths.YAMLS.glob("ART_*.yaml")):
        rows.append(audit_yaml_file(yp, threshold=threshold))

    df = pd.DataFrame(rows)

    out_path: Optional[Path] = None
    if export:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = paths.CONSOLIDATED / f"qa_report_{ts}.csv"
        df.to_csv(out_path, index=False, sep=";", encoding="utf-8")

    return df, out_path

