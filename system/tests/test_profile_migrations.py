from __future__ import annotations

import pytest

from profile_engine.migrations import migrate_profile_payload
from profile_engine.models import CURRENT_PROFILE_SCHEMA_VERSION


def test_migrate_legacy_payload_maps_old_keys() -> None:
    raw = {
        "meta": {"profile_id": "legacy", "version": "0.9", "name": "Legacy"},
        "fields": [{"field_id": "ArtigoID", "kind": "string"}],
        "rules": [
            {
                "rule_id": "R1",
                "if": "True",
                "assert_expr": "True",
                "severity": "error",
                "message": "ok",
            }
        ],
        "quotes": {"enabled": False},
        "prompt": "return yaml",
    }

    migrated, notes = migrate_profile_payload(raw)

    assert migrated["schema_version"] == CURRENT_PROFILE_SCHEMA_VERSION
    profile = migrated["profile"]
    assert profile["fields"][0]["id"] == "ArtigoID"
    assert profile["fields"][0]["type"] == "string"
    assert profile["rules"][0]["id"] == "R1"
    assert "quotes_policy" in profile
    assert "prompt_contract" in profile
    assert any("migrated" in note for note in notes)


def test_migrate_keeps_current_schema() -> None:
    raw = {
        "schema_version": CURRENT_PROFILE_SCHEMA_VERSION,
        "profile": {
            "meta": {"profile_id": "p", "version": "1.0.0", "name": "P"},
            "fields": [{"id": "ArtigoID", "type": "string"}],
            "rules": [],
            "quotes_policy": {"enabled": False},
            "output": {"format": "yaml"},
            "prompt_contract": {"instructions": []},
        },
    }

    migrated, _notes = migrate_profile_payload(raw)

    assert migrated["schema_version"] == CURRENT_PROFILE_SCHEMA_VERSION
    assert migrated["profile"]["meta"]["profile_id"] == "p"


def test_migrate_raises_for_unsupported_schema() -> None:
    with pytest.raises(ValueError):
        migrate_profile_payload({"schema_version": "99.0", "profile": {}})

