from __future__ import annotations

from presets import get_preset


def test_get_preset_returns_named_preset() -> None:
    assert get_preset("batch").name == "batch"


def test_get_preset_falls_back_to_pilot() -> None:
    assert get_preset("does-not-exist").name == "pilot"
