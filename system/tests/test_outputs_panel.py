from __future__ import annotations

from datetime import timezone
from pathlib import Path

import gui.panel_outputs as panel_outputs_module
from gui.panel_outputs import OutputEntry, OutputsPanel


class _TreeWithoutIndex:
    def selection(self) -> tuple[str, ...]:
        return ("row-2",)

    def index(self, _iid: str) -> int:
        raise AssertionError("Tree index lookup should not be used for selection")


def test_selected_entry_uses_iid_mapping() -> None:
    entry = OutputEntry(
        path=Path("example.yaml"),
        file_type="YAML",
        size=123,
        modified=1.0,
    )
    panel = object.__new__(OutputsPanel)
    panel._tree = _TreeWithoutIndex()
    panel._row_entry_by_iid = {"row-2": entry}

    selected = OutputsPanel._selected_entry(panel)

    assert selected == entry


def test_format_modified_uses_explicit_utc_timezone(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class _FakeAwareTime:
        def astimezone(self):
            return self

        def strftime(self, fmt: str) -> str:
            calls["fmt"] = fmt
            return "2026-02-17 10:00"

    class _FakeDateTime:
        @classmethod
        def fromtimestamp(cls, ts: float, tz=None):  # noqa: ANN001
            calls["ts"] = ts
            calls["tz"] = tz
            return _FakeAwareTime()

    monkeypatch.setattr(panel_outputs_module, "datetime", _FakeDateTime)

    panel = object.__new__(OutputsPanel)
    formatted = OutputsPanel._format_modified(panel, 123.4)

    assert formatted == "2026-02-17 10:00"
    assert calls["ts"] == 123.4
    assert calls["tz"] is timezone.utc
