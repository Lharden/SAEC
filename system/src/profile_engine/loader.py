"""Loader utilities for profile declarations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .migrations import migrate_profile_payload
from .models import ProfileSpec
from .validator import validate_rule_expressions


@dataclass(frozen=True)
class ProfileLoadError(Exception):
    """Raised when a profile declaration cannot be loaded."""

    message: str
    errors: tuple[str, ...] = ()

    def __str__(self) -> str:
        if not self.errors:
            return self.message
        details = "; ".join(self.errors)
        return f"{self.message}: {details}"


def load_profile_spec(profile_path: Path) -> ProfileSpec:
    """Load and validate one profile spec file."""
    path = Path(profile_path).resolve()
    if not path.exists():
        raise ProfileLoadError(f"Profile file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileLoadError(
            f"Invalid YAML profile at {path}",
            errors=(str(exc),),
        ) from exc
    except OSError as exc:
        raise ProfileLoadError(f"Failed to read profile file: {path}") from exc

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ProfileLoadError(
            f"Profile root must be a mapping (dict): {path}",
            errors=(f"got {type(raw).__name__}",),
        )

    try:
        migrated_raw, _migration_notes = migrate_profile_payload(raw)
    except ValueError as exc:
        raise ProfileLoadError(
            f"Profile schema migration failed for {path}",
            errors=(str(exc),),
        ) from exc

    spec = ProfileSpec.from_dict(migrated_raw)
    errors = spec.validate_structure()
    errors.extend(validate_rule_expressions(spec.rules))
    if errors:
        raise ProfileLoadError(
            f"Profile structure validation failed for {path}",
            errors=tuple(errors),
        )
    return spec


def dump_profile_spec(spec: ProfileSpec) -> dict[str, Any]:
    """Serialize profile model back to dict."""
    return spec.to_dict()
