"""Utilidades compartilhadas para QA."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_qa_ok_ids(qa_report_path: Path) -> set[str]:
    """Carrega ArtigoID com status OK do relatório de QA."""
    if not qa_report_path.exists():
        raise FileNotFoundError(f"QA report not found: {qa_report_path}")
    df = pd.read_csv(qa_report_path, sep=";")
    if "ArtigoID" not in df.columns or "status" not in df.columns:
        raise ValueError("qa_report must contain columns: ArtigoID, status")
    rows = df.to_dict(orient="records")
    return {
        str(r.get("ArtigoID", "")).strip()
        for r in rows
        if str(r.get("status", "")).strip().upper() == "OK"
    }
