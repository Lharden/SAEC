"""requote_from_texts.py

Gera/atualiza Quotes em YAMLs usando o texts.json (texto extraído do PDF).

Objetivo
--------
Substituir quotes placeholder ou pouco rastreáveis por trechos reais do texts.json,
para melhorar alinhamento ao Guia v3.3 sem depender de LLM.

Notas
-----
- Heurística baseada em palavras-chave (Contexto/Intervenção/Método/Mecanismo/Outcome/Limitação)
- Página preenchida como p.<n>, onde <n> é a key do texts.json
- Mantém no máximo 8 quotes e no mínimo 3

Uso (notebook)
--------------
from requote_from_texts import requote_failed
log_df, log_path = requote_failed(qa_df, threshold=80)

Requisitos
----------
- PyYAML
- rapidfuzz
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml
from rapidfuzz import fuzz

def _load_paths():
    try:
        from .config import paths as cfg_paths
    except ImportError:  # pragma: no cover - standalone usage
        from config import paths as cfg_paths
    return cfg_paths


paths = _load_paths()


ALLOWED_TIPO_QUOTE = {
    "Contexto",
    "Intervenção",
    "Mecanismo",
    "Outcome",
    "Limitação",
    "Método",
    "Outro",
}


def _norm(s: Any) -> str:
    if s is None:
        return ""
    t = str(s).replace("\u00a0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _load_yaml(path: Path) -> Dict[str, Any]:
    doc = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))[0]
    if not isinstance(doc, dict):
        raise ValueError("YAML não é dict")
    return doc


def _dump_yaml(doc: Dict[str, Any]) -> str:
    body = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)
    return "---\n" + body.strip() + "\n---\n"


def _load_texts_json(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if v is None:
                continue
            out[str(k)] = str(v)
    return out


def _split_sentences(text: str) -> List[str]:
    t = _norm(text)
    t = re.sub(r"-\s+", "", t)  # des-hifeniza quebra de linha
    raw = re.split(r"(?<=[\.!\?])\s+", t)
    out = []
    for s in raw:
        s = s.strip()
        if len(s) < 20:
            continue
        if len(s) > 400:
            s = s[:400].rstrip() + "..."
        out.append(s)
    return out


KEYWORDS = {
    "Contexto": ["industry", "sector", "supply chain", "context", "background", "challenge", "oil and gas", "o&g", "risk"],
    "Intervenção": ["we propose", "we develop", "we present", "framework", "approach", "system", "workflow", "model"],
    "Método": ["method", "methodology", "dataset", "data", "experiment", "case study", "survey", "interview", "training"],
    "Outcome": ["results", "we achieved", "improved", "improvement", "reduction", "accuracy", "mae", "rmse", "%", "performance"],
    "Limitação": ["limitation", "limited", "restricted", "constraint", "future work", "however", "may not", "cannot"],
    "Mecanismo": ["enables", "allows", "by leveraging", "therefore", "thus", "as a result", "captures", "proactive"],
}


def _score_sentence(sent: str, tipo: str) -> int:
    s = sent.lower()
    score = sum(1 for kw in KEYWORDS.get(tipo, []) if kw in s)
    if tipo == "Outcome" and re.search(r"\d", s):
        score += 2
    if re.search(r"\[[0-9]{1,3}\]", sent):
        score -= 1
    return score


@dataclass
class Candidate:
    tipo: str
    sent: str
    page_id: str
    score: int


def _build_candidates(pages: Dict[str, str]) -> List[Candidate]:
    cands: List[Candidate] = []
    for pid, text in pages.items():
        for sent in _split_sentences(text):
            for tipo in ("Contexto", "Intervenção", "Mecanismo", "Outcome", "Limitação", "Método"):
                sc = _score_sentence(sent, tipo)
                if sc >= 2:
                    cands.append(Candidate(tipo=tipo, sent=sent, page_id=pid, score=sc))
    return cands


def _choose_quotes(cands: List[Candidate], max_quotes: int = 8) -> List[Dict[str, Any]]:
    cands = sorted(cands, key=lambda c: (c.score, len(c.sent)), reverse=True)

    chosen: List[Candidate] = []
    used = set()

    desired_order = ["Contexto", "Intervenção", "Método", "Mecanismo", "Outcome", "Limitação"]

    for tipo in desired_order:
        for c in cands:
            if c.tipo != tipo:
                continue
            key = c.sent.lower()
            if key in used:
                continue
            chosen.append(c)
            used.add(key)
            break

    for c in cands:
        if len(chosen) >= max_quotes:
            break
        key = c.sent.lower()
        if key in used:
            continue
        chosen.append(c)
        used.add(key)

    if len(chosen) < 3:
        for c in cands:
            if len(chosen) >= 3:
                break
            key = c.sent.lower()
            if key in used:
                continue
            chosen.append(c)
            used.add(key)

    out: List[Dict[str, Any]] = []
    for i, c in enumerate(chosen[:max_quotes], start=1):
        tipo = c.tipo if c.tipo in ALLOWED_TIPO_QUOTE else "Outro"
        out.append({
            "QuoteID": f"Q{i:03d}",
            "TipoQuote": tipo,
            "Trecho": c.sent,
            "Página": f"p.{c.page_id}",
        })
    return out


def requote_one(artigo_id: str, threshold: float = 80.0, force: bool = True) -> Tuple[bool, str]:
    """Regera quotes de um artigo a partir do texts.json.

    Atualmente fazemos force=True por padrão quando chamado a partir do QA FAIL.
    """
    yaml_path = paths.YAMLS / f"{artigo_id}.yaml"
    if not yaml_path.exists():
        return False, "yaml não encontrado"

    doc = _load_yaml(yaml_path)
    texts_path = paths.WORK / artigo_id / "texts.json"
    if not texts_path.exists():
        return False, "texts.json ausente"

    pages = _load_texts_json(texts_path)
    cands = _build_candidates(pages)
    if not cands:
        return False, "sem candidatos (keywords)"

    doc["Quotes"] = _choose_quotes(cands, max_quotes=8)
    yaml_path.write_text(_dump_yaml(doc), encoding="utf-8")
    return True, "requote aplicado"


def _best_match_page_for_quote(trecho: str, pages: Dict[str, str]) -> Tuple[float, Optional[str]]:
    needle = _norm(trecho).lower()
    if len(needle) < 10:
        return 0.0, None
    best = 0.0
    best_page = None
    for pid, text in pages.items():
        hay = _norm(text).lower()
        if not hay:
            continue
        s = float(fuzz.partial_ratio(needle, hay))
        if s > best:
            best = s
            best_page = pid
    return best, best_page


def fill_pages(artigo_id: str, threshold: float = 80.0, force_file_pages: bool = False) -> Tuple[bool, str]:
    """Preenche/normaliza Página das quotes usando o texts.json como referência.

    - Por padrão, só preenche quando Página está em NR.
    - Se force_file_pages=True, sobrescreve Página para sempre ser a página do arquivo (p.<id do texts.json>),
      desde que o trecho tenha match >= threshold.

    Observação:
    - Isso não tenta recuperar paginação do *volume* (ex.: 506). A ideia é localização no arquivo local.
    """
    yaml_path = paths.YAMLS / f"{artigo_id}.yaml"
    if not yaml_path.exists():
        return False, "yaml não encontrado"

    doc = _load_yaml(yaml_path)
    texts_path = paths.WORK / artigo_id / "texts.json"
    if not texts_path.exists():
        return False, "texts.json ausente"

    pages = _load_texts_json(texts_path)
    quotes = doc.get("Quotes") or []
    if not isinstance(quotes, list):
        return False, "Quotes não é lista"

    changed = False
    updated = 0
    attempted = 0

    for q in quotes:
        if not isinstance(q, dict):
            continue

        trecho = _norm(q.get("Trecho", ""))
        if len(trecho.strip()) < 10:
            continue

        page_field = _norm(q.get("Página", ""))
        needs = ("nr" in page_field.lower()) or force_file_pages
        if not needs:
            continue

        attempted += 1
        score, pid = _best_match_page_for_quote(trecho, pages)
        if pid and score >= threshold:
            new_page = f"p.{pid}"
            if _norm(q.get("Página", "")) != new_page:
                q["Página"] = new_page
                changed = True
                updated += 1

    if changed:
        doc["Quotes"] = quotes
        yaml_path.write_text(_dump_yaml(doc), encoding="utf-8")
        return True, f"pages normalizadas ({updated}/{attempted})"

    return False, f"nada a fazer ({updated}/{attempted})"


def requote_failed(qa_df: pd.DataFrame, threshold: float = 80.0) -> Tuple[pd.DataFrame, Path]:
    """Roda requote nos artigos com status FAIL no qa_df.

    Otimização: se não houver FAIL, retorna um log vazio e não altera nada.
    """
    fail_ids = [x for x in qa_df.loc[qa_df["status"] == "FAIL", "ArtigoID"].tolist() if isinstance(x, str)]

    logs: List[Dict[str, Any]] = []

    if not fail_ids:
        out_df = pd.DataFrame(columns=["ArtigoID", "action", "changed", "msg"])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = paths.CONSOLIDATED / f"requote_failed_log_{ts}.csv"
        out_df.to_csv(out_path, index=False, sep=";", encoding="utf-8")
        return out_df, out_path

    for art_id in fail_ids:
        changed, msg = requote_one(art_id, threshold=threshold, force=True)
        logs.append({"ArtigoID": art_id, "action": "requote_failed", "changed": changed, "msg": msg})

    out_df = pd.DataFrame(logs)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = paths.CONSOLIDATED / f"requote_failed_log_{ts}.csv"
    out_df.to_csv(out_path, index=False, sep=";", encoding="utf-8")
    return out_df, out_path


def fix_review(qa_df: pd.DataFrame, threshold: float = 80.0, force_file_pages: bool = True) -> Tuple[pd.DataFrame, Path]:
    """Auto-fix para REVIEW.

    Estratégia:
    - Normaliza páginas para serem SEMPRE a página do arquivo (p.<id do texts.json>) quando possível.
    - Se ainda está REVIEW por match_rate baixo: aplica requote_one (force).

    Obs: não mexe em OK.
    """
    review_ids = [x for x in qa_df.loc[qa_df["status"] == "REVIEW", "ArtigoID"].tolist() if isinstance(x, str)]

    logs: List[Dict[str, Any]] = []
    for art_id in review_ids:
        c1, m1 = fill_pages(art_id, threshold=threshold, force_file_pages=force_file_pages)
        logs.append({"ArtigoID": art_id, "action": "fill_pages(file_page)", "changed": c1, "msg": m1})

        row = qa_df.loc[qa_df["ArtigoID"] == art_id].head(1)
        reasons = str(row["reasons"].iloc[0]) if not row.empty else ""
        if "match_rate" in reasons:
            c2, m2 = requote_one(art_id, threshold=threshold, force=True)
            logs.append({"ArtigoID": art_id, "action": "requote_review", "changed": c2, "msg": m2})

    out_df = pd.DataFrame(logs)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = paths.CONSOLIDATED / f"review_fix_log_{ts}.csv"
    out_df.to_csv(out_path, index=False, sep=";", encoding="utf-8")
    return out_df, out_path


def enforce_file_pages_all(threshold: float = 80.0) -> Tuple[pd.DataFrame, Path]:
    """Aplica normalização de página (p.<arquivo>) em TODOS os YAMLs.

    Isso garante consistência: a página sempre referencia a página do arquivo local/texts.json,
    não a paginação global do volume.
    """
    logs: List[Dict[str, Any]] = []
    for yp in sorted(paths.YAMLS.glob('ART_*.yaml')):
        art_id = yp.stem
        changed, msg = fill_pages(art_id, threshold=threshold, force_file_pages=True)
        logs.append({"ArtigoID": art_id, "changed": changed, "msg": msg})

    out_df = pd.DataFrame(logs)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = paths.CONSOLIDATED / f"enforce_file_pages_log_{ts}.csv"
    out_df.to_csv(out_path, index=False, sep=';', encoding='utf-8')
    return out_df, out_path
