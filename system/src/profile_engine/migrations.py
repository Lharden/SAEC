"""Schema version migration helpers for declarative profile payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import CURRENT_PROFILE_SCHEMA_VERSION


_LEGACY_VERSIONS = {"", "0", "0.0", "legacy", "v0"}
_CURRENT_VERSION_ALIASES = {CURRENT_PROFILE_SCHEMA_VERSION, "1", "1.0.0"}


def _normalize_schema_version(value: str) -> str:
    clean = (value or "").strip().lower()
    if clean in _LEGACY_VERSIONS:
        return "0"
    if clean in {alias.lower() for alias in _CURRENT_VERSION_ALIASES}:
        return CURRENT_PROFILE_SCHEMA_VERSION
    return clean


def _maybe_wrap_legacy_profile_root(payload: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    if isinstance(payload.get("profile"), dict):
        return payload
    legacy_keys = {
        "meta",
        "topics",
        "fields",
        "rules",
        "quotes_policy",
        "output",
        "prompt_contract",
        "tests",
    }
    if any(key in payload for key in legacy_keys):
        wrapped = {"profile": payload}
        if "schema_version" in payload:
            wrapped["schema_version"] = payload["schema_version"]
        notes.append("wrapped legacy root keys under profile")
        return wrapped
    payload["profile"] = {}
    return payload


def _migrate_fields(profile: dict[str, Any], notes: list[str]) -> None:
    fields = profile.get("fields", [])
    if not isinstance(fields, list):
        return
    migrated = False
    for item in fields:
        if not isinstance(item, dict):
            continue
        if "id" not in item and "field_id" in item:
            item["id"] = item.pop("field_id")
            migrated = True
        if "type" not in item and "kind" in item:
            item["type"] = item.pop("kind")
            migrated = True
    if migrated:
        notes.append("migrated legacy field keys to id/type")


def _migrate_rules(profile: dict[str, Any], notes: list[str]) -> None:
    rules = profile.get("rules", [])
    if not isinstance(rules, list):
        return
    migrated = False
    for item in rules:
        if not isinstance(item, dict):
            continue
        if "id" not in item and "rule_id" in item:
            item["id"] = item.pop("rule_id")
            migrated = True
        if "when" not in item and "if" in item:
            item["when"] = item.pop("if")
            migrated = True
        if "assert" not in item and "assert_expr" in item:
            item["assert"] = item.pop("assert_expr")
            migrated = True
    if migrated:
        notes.append("migrated legacy rule keys to id/when/assert")


def _migrate_quotes_policy(profile: dict[str, Any], notes: list[str]) -> None:
    if "quotes_policy" in profile:
        return
    quotes = profile.get("quotes")
    if isinstance(quotes, dict):
        profile["quotes_policy"] = quotes
        notes.append("migrated profile.quotes to profile.quotes_policy")


def _migrate_prompt_contract(profile: dict[str, Any], notes: list[str]) -> None:
    if "prompt_contract" in profile:
        return
    prompt = profile.get("prompt")
    if isinstance(prompt, dict):
        profile["prompt_contract"] = prompt
        notes.append("migrated profile.prompt to profile.prompt_contract")
        return
    if isinstance(prompt, str) and prompt.strip():
        profile["prompt_contract"] = {
            "return_only_output": True,
            "include_self_review": True,
            "instructions": [prompt.strip()],
        }
        notes.append("migrated profile.prompt string to prompt_contract.instructions")


def migrate_profile_payload(raw: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Normalize one profile payload to current schema version."""
    payload = deepcopy(raw)
    notes: list[str] = []
    payload = _maybe_wrap_legacy_profile_root(payload, notes)
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        profile = {}
        payload["profile"] = profile

    schema_raw = str(
        payload.get("schema_version", profile.get("schema_version", ""))
    )
    schema_version = _normalize_schema_version(schema_raw)
    if schema_version not in {"0", CURRENT_PROFILE_SCHEMA_VERSION}:
        raise ValueError(
            "unsupported schema_version "
            f"'{schema_raw or '<missing>'}' (supported: "
            f"{CURRENT_PROFILE_SCHEMA_VERSION} or legacy)"
        )

    if schema_version == "0":
        _migrate_fields(profile, notes)
        _migrate_rules(profile, notes)
        _migrate_quotes_policy(profile, notes)
        _migrate_prompt_contract(profile, notes)
        if "output" not in profile:
            profile["output"] = {"format": "yaml"}
            notes.append("added default output contract for legacy profile")
        if "prompt_contract" not in profile:
            profile["prompt_contract"] = {
                "return_only_output": True,
                "include_self_review": True,
                "instructions": [],
            }
            notes.append("added default prompt contract for legacy profile")

    payload["schema_version"] = CURRENT_PROFILE_SCHEMA_VERSION
    if isinstance(profile, dict) and "schema_version" in profile:
        profile.pop("schema_version", None)
        notes.append("removed nested profile.schema_version in favor of root field")
    return payload, tuple(notes)

