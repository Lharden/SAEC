"""mapping_sync.py

Utilities to keep Extraction/mapping.csv consistent with the state of outputs.

Rationale
---------
The mapping.csv file is updated during the extraction step (notebook 03) when
save_approved() is called. If YAMLs are repaired later (e.g., QA-driven fixes,
manual edits, requote), mapping.csv may become stale.

This module provides deterministic reconciliation based on existing artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import importlib


def _load_qa_ok_ids(qa_report_path: Path) -> set[str]:
    try:
        mod = importlib.import_module(".qa_utils", package=__package__)
    except Exception:  # pragma: no cover - standalone usage
        mod = importlib.import_module("qa_utils")
    return mod.load_qa_ok_ids(qa_report_path)


@dataclass(frozen=True)
class SyncPolicy:
    processed_value: str = "Sim"
    not_processed_value: str = "Não"
    approved_status: str = "Aprovado"


def _discover_yaml_ids(yamls_dir: Path) -> set[str]:
    return {p.stem for p in yamls_dir.glob("ART_*.yaml")}


def _load_mapping_df(mapping_path: Path) -> pd.DataFrame:
    df = pd.read_csv(mapping_path)
    if "ArtigoID" not in df.columns:
        raise ValueError("mapping.csv must contain column: ArtigoID")
    for col in ("Processado", "Status"):
        if col not in df.columns:
            df[col] = ""
    return df


def _load_valid_yaml_ids(yamls_dir: Path) -> set[str]:
    import importlib

    try:
        validators_mod = importlib.import_module(".validators", package=__package__)
    except Exception:  # pragma: no cover - standalone usage
        validators_mod = importlib.import_module("validators")

    validate_yaml_file = validators_mod.validate_yaml_file

    valid_ids: set[str] = set()
    for path in yamls_dir.glob("ART_*.yaml"):
        try:
            result = validate_yaml_file(path)
            if result.is_valid:
                valid_ids.add(path.stem)
        except Exception:
            # Se não for possível validar, não promover o artigo.
            continue
    return valid_ids


def sync_mapping_with_validation(
    *,
    mapping_path: Path,
    yamls_dir: Path,
    dry_run: bool = True,
    policy: SyncPolicy = SyncPolicy(),
) -> pd.DataFrame:
    """Synchronize mapping.csv based on YAML validation.

    Rules:
    - If YAML exists and passes validation, mark Processado=Sim and Status=Aprovado.
    - Otherwise, leave the row unchanged.
    """
    mapping_path = Path(mapping_path)
    yamls_dir = Path(yamls_dir)

    if not mapping_path.exists():
        raise FileNotFoundError(f"mapping.csv not found: {mapping_path}")
    if not yamls_dir.exists():
        raise FileNotFoundError(f"YAML directory not found: {yamls_dir}")

    df = _load_mapping_df(mapping_path)
    valid_ids = _load_valid_yaml_ids(yamls_dir)

    changes = []
    changed_any = False

    for i, row in df.iterrows():
        art_id = str(row.get("ArtigoID", "")).strip()
        if not art_id or art_id not in valid_ids:
            continue

        old_proc = str(row.get("Processado", ""))
        old_status = str(row.get("Status", ""))

        new_proc = policy.processed_value
        new_status = policy.approved_status

        will_change = (old_proc != new_proc) or (old_status != new_status)
        if will_change:
            changed_any = True
            df.at[i, "Processado"] = new_proc
            df.at[i, "Status"] = new_status

        changes.append(
            {
                "ArtigoID": art_id,
                "valid_yaml": True,
                "Processado_before": old_proc,
                "Status_before": old_status,
                "Processado_after": new_proc,
                "Status_after": new_status,
                "changed": bool(will_change),
            }
        )

    out = pd.DataFrame(changes).sort_values("ArtigoID") if changes else pd.DataFrame(
        columns=[
            "ArtigoID",
            "valid_yaml",
            "Processado_before",
            "Status_before",
            "Processado_after",
            "Status_after",
            "changed",
        ]
    )

    if (not dry_run) and changed_any:
        df.to_csv(mapping_path, index=False, encoding="utf-8")

    return out


def sync_mapping_with_qa_report(
    *,
    mapping_path: Path,
    qa_report_path: Path,
    dry_run: bool = True,
    policy: SyncPolicy = SyncPolicy(),
) -> pd.DataFrame:
    """Synchronize mapping.csv based on QA report (status == OK)."""
    mapping_path = Path(mapping_path)
    qa_report_path = Path(qa_report_path)

    if not mapping_path.exists():
        raise FileNotFoundError(f"mapping.csv not found: {mapping_path}")

    df = _load_mapping_df(mapping_path)
    ok_ids = _load_qa_ok_ids(qa_report_path)

    changes = []
    changed_any = False

    for i, row in df.iterrows():
        art_id = str(row.get("ArtigoID", "")).strip()
        if not art_id or art_id not in ok_ids:
            continue

        old_proc = str(row.get("Processado", ""))
        old_status = str(row.get("Status", ""))

        new_proc = policy.processed_value
        new_status = policy.approved_status

        will_change = (old_proc != new_proc) or (old_status != new_status)
        if will_change:
            changed_any = True
            df.at[i, "Processado"] = new_proc
            df.at[i, "Status"] = new_status

        changes.append(
            {
                "ArtigoID": art_id,
                "qa_ok": True,
                "Processado_before": old_proc,
                "Status_before": old_status,
                "Processado_after": new_proc,
                "Status_after": new_status,
                "changed": bool(will_change),
            }
        )

    out = pd.DataFrame(changes).sort_values("ArtigoID") if changes else pd.DataFrame(
        columns=[
            "ArtigoID",
            "qa_ok",
            "Processado_before",
            "Status_before",
            "Processado_after",
            "Status_after",
            "changed",
        ]
    )

    if (not dry_run) and changed_any:
        df.to_csv(mapping_path, index=False, encoding="utf-8")

    return out


def sync_mapping_with_validation_and_qa(
    *,
    mapping_path: Path,
    yamls_dir: Path,
    qa_report_path: Path,
    dry_run: bool = True,
    policy: SyncPolicy = SyncPolicy(),
) -> pd.DataFrame:
    """Synchronize mapping.csv using BOTH validation and QA (status OK).

    Conservative rule: only approve if YAML is valid AND QA status == OK.
    """
    mapping_path = Path(mapping_path)
    yamls_dir = Path(yamls_dir)
    qa_report_path = Path(qa_report_path)

    if not mapping_path.exists():
        raise FileNotFoundError(f"mapping.csv not found: {mapping_path}")
    if not yamls_dir.exists():
        raise FileNotFoundError(f"YAML directory not found: {yamls_dir}")

    df = _load_mapping_df(mapping_path)
    valid_ids = _load_valid_yaml_ids(yamls_dir)
    ok_ids = _load_qa_ok_ids(qa_report_path)

    approve_ids = valid_ids.intersection(ok_ids)

    changes = []
    changed_any = False

    for i, row in df.iterrows():
        art_id = str(row.get("ArtigoID", "")).strip()
        if not art_id or art_id not in approve_ids:
            continue

        old_proc = str(row.get("Processado", ""))
        old_status = str(row.get("Status", ""))

        new_proc = policy.processed_value
        new_status = policy.approved_status

        will_change = (old_proc != new_proc) or (old_status != new_status)
        if will_change:
            changed_any = True
            df.at[i, "Processado"] = new_proc
            df.at[i, "Status"] = new_status

        changes.append(
            {
                "ArtigoID": art_id,
                "valid_yaml": True,
                "qa_ok": True,
                "Processado_before": old_proc,
                "Status_before": old_status,
                "Processado_after": new_proc,
                "Status_after": new_status,
                "changed": bool(will_change),
            }
        )

    out = pd.DataFrame(changes).sort_values("ArtigoID") if changes else pd.DataFrame(
        columns=[
            "ArtigoID",
            "valid_yaml",
            "qa_ok",
            "Processado_before",
            "Status_before",
            "Processado_after",
            "Status_after",
            "changed",
        ]
    )

    if (not dry_run) and changed_any:
        df.to_csv(mapping_path, index=False, encoding="utf-8")

    return out
