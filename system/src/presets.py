"""Execution presets for UI quick selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    mode: str
    step: int | None
    dry_run: bool
    force: bool
    timeout_minutes: float
    description: str


PRESETS: dict[str, Preset] = {
    "pilot": Preset(
        name="pilot",
        mode="step",
        step=2,
        dry_run=False,
        force=False,
        timeout_minutes=10.0,
        description="Ingest one article and validate setup.",
    ),
    "batch": Preset(
        name="batch",
        mode="all",
        step=None,
        dry_run=False,
        force=False,
        timeout_minutes=60.0,
        description="Run full pipeline with standard safety flags.",
    ),
    "local_only": Preset(
        name="local_only",
        mode="all",
        step=None,
        dry_run=False,
        force=False,
        timeout_minutes=60.0,
        description="Run full flow preferring local models and local resources.",
    ),
    "api_only": Preset(
        name="api_only",
        mode="all",
        step=None,
        dry_run=False,
        force=False,
        timeout_minutes=60.0,
        description="Run full flow using API providers only.",
    ),
}


def list_presets() -> list[Preset]:
    return [PRESETS[key] for key in sorted(PRESETS.keys())]


def get_preset(name: str) -> Preset:
    return PRESETS[name]
