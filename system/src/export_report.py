"""Summary export utilities for extracted YAML outputs."""

from __future__ import annotations

import csv
from datetime import datetime, UTC
import html
from pathlib import Path
from typing import Any

import yaml


def _first_non_empty(data: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def _extract_quality_score(data: dict[str, Any]) -> float | None:
    keys = ["QualityScore", "Quality_Score", "Qualidade", "QualidadeScore"]
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _cimo_counts(data: dict[str, Any]) -> tuple[int, int, int, int]:
    c_keys = ["ProblemaNegócio_Contexto", "Contexto", "Context"]
    i_keys = ["Intervenção_Descrição", "Intervencao", "Intervention"]
    m_keys = ["Mecanismo_Estruturado", "Mecanismo_Declarado", "Mechanism"]
    o_keys = ["Resultados_Quant", "Resultados_Qual", "Outcome", "Resultado"]

    def _count(keys: list[str]) -> int:
        return sum(1 for key in keys if str(data.get(key, "")).strip())

    return (_count(c_keys), _count(i_keys), _count(m_keys), _count(o_keys))


def _infer_status(data: dict[str, Any]) -> str:
    c_count, i_count, m_count, o_count = _cimo_counts(data)
    if min(c_count, i_count, m_count, o_count) > 0:
        return "complete"
    if any((c_count, i_count, m_count, o_count)):
        return "partial"
    return "empty"


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    docs = list(yaml.safe_load_all(raw))
    for payload in docs:
        if isinstance(payload, dict):
            return payload
    return {}


def generate_summary_rows(yamls_dir: Path) -> list[dict[str, str]]:
    """Build summary rows from YAML files in *yamls_dir*."""
    rows: list[dict[str, str]] = []
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    for path in sorted(yamls_dir.glob("*.yaml")):
        try:
            data = _load_yaml(path)
            article_id = str(data.get("ArtigoID") or path.stem)
            title = _first_non_empty(
                data,
                ["Title", "Titulo", "Título", "Referência_Curta", "Referencia_Curta"],
                default=path.stem,
            )
            c_count, i_count, m_count, o_count = _cimo_counts(data)
            quality = _extract_quality_score(data)
            status = _infer_status(data)
            rows.append(
                {
                    "Article ID": article_id,
                    "Title": title,
                    "Status": status,
                    "C count": str(c_count),
                    "I count": str(i_count),
                    "M count": str(m_count),
                    "O count": str(o_count),
                    "Quality Score": "" if quality is None else f"{quality:.2f}",
                    "Timestamp": timestamp,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "Article ID": path.stem,
                    "Title": path.name,
                    "Status": f"error: {exc}",
                    "C count": "0",
                    "I count": "0",
                    "M count": "0",
                    "O count": "0",
                    "Quality Score": "",
                    "Timestamp": timestamp,
                }
            )

    return rows


def export_summary_csv(yamls_dir: Path, output_csv: Path) -> int:
    """Export YAML summary report to CSV and return row count."""
    rows = generate_summary_rows(yamls_dir)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Article ID",
                "Title",
                "Status",
                "C count",
                "I count",
                "M count",
                "O count",
                "Quality Score",
                "Timestamp",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def export_summary_html(yamls_dir: Path, output_html: Path) -> int:
    """Export YAML summary report to a simple HTML table."""
    rows = generate_summary_rows(yamls_dir)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    def _row_class(status: str) -> str:
        if status.startswith("error"):
            return "err"
        if status == "complete":
            return "ok"
        if status == "partial":
            return "warn"
        return "neutral"

    lines = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'><title>SAEC Summary</title>",
        "<style>",
        "body{font-family:Segoe UI,Arial,sans-serif;margin:18px}",
        "table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #aaa;padding:6px;text-align:left}",
        "th{background:#ececec}",
        "tr.ok{background:#e7f7e7}",
        "tr.warn{background:#fff9e0}",
        "tr.err{background:#fde8e8}",
        "</style></head><body>",
        "<h2>SAEC Summary Report</h2>",
        "<table><thead><tr>",
    ]

    headers = [
        "Article ID",
        "Title",
        "Status",
        "C count",
        "I count",
        "M count",
        "O count",
        "Quality Score",
        "Timestamp",
    ]
    lines.append("".join(f"<th>{h}</th>" for h in headers))
    lines.append("</tr></thead><tbody>")

    for row in rows:
        klass = _row_class(row["Status"])
        lines.append(f"<tr class='{klass}'>")
        lines.append(
            "".join(f"<td>{html.escape(str(row[h]))}</td>" for h in headers)
        )
        lines.append("</tr>")

    lines.extend(["</tbody></table></body></html>"])
    output_html.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)

