from __future__ import annotations

from pathlib import Path
import tkinter as tk

import pytest

import gui.app as app_module
from gui.app import SAECWin98App
from gui.layout_main import build_main_layout


def _ensure_tk() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk not available in test environment: {exc}")
    root.withdraw()
    root.destroy()


def test_layout_build_smoke() -> None:
    _ensure_tk()

    root = tk.Tk()
    root.withdraw()
    try:
        layout = build_main_layout(root, on_run=lambda: None, on_cancel=lambda: None)
        assert layout.run_panel is not None
        assert layout.queue_panel is not None
        assert layout.outputs_panel is not None
        assert layout.logs_panel is not None
        assert layout.diagnostics_panel is not None
        assert layout.profile_panel is not None
        assert layout.right_notebook.index("end") == 5
    finally:
        root.destroy()


def test_bind_shortcuts_registers_expected_sequences() -> None:
    class FakeWindow:
        def __init__(self) -> None:
            self.bindings: list[str] = []

        def bind_all(self, sequence: str, _handler) -> None:
            self.bindings.append(sequence)

        def _shortcut_run(self, _event=None) -> str:
            return "break"

        def _shortcut_cancel(self, _event=None) -> str:
            return "break"

        def _shortcut_clear_logs(self, _event=None) -> str:
            return "break"

        def _shortcut_workspace(self, _event=None) -> str:
            return "break"

        def _shortcut_refresh(self, _event=None) -> str:
            return "break"

        def _shortcut_quit(self, _event=None) -> str:
            return "break"

        def _shortcut_help(self, _event=None) -> str:
            return "break"

    fake = FakeWindow()
    SAECWin98App._bind_shortcuts(fake)  # type: ignore[arg-type]

    assert set(fake.bindings) == {
        "<Control-r>",
        "<Control-Shift-C>",
        "<Control-Shift-c>",
        "<Control-l>",
        "<Control-w>",
        "<F5>",
        "<Control-q>",
        "<F1>",
    }


def test_app_startup_shutdown_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_tk()

    class InMemorySettingsStore:
        def __init__(self, base_dir: Path) -> None:
            self.base_dir = base_dir
            self._data: dict[str, object] = {}

        def load(self) -> dict[str, object]:
            return dict(self._data)

        def save(self, data: dict[str, object]) -> None:
            self._data = dict(data)

        def save_window_state(self, **kwargs: object) -> None:
            self._data.update(kwargs)

        def add_recent_workspace(self, _workspace: Path) -> dict[str, object]:
            return dict(self._data)

        def set_last_project(self, _workspace_root: Path, _project_id: str) -> None:
            return

    monkeypatch.setattr(app_module, "SettingsStore", InMemorySettingsStore)
    monkeypatch.setattr(app_module, "apply_win98_theme", lambda _root: None)
    monkeypatch.setattr(app_module, "setup_logging", lambda **_kwargs: None)

    app = SAECWin98App()
    try:
        app.withdraw()
        app.update_idletasks()
        assert app.layout.run_panel is not None
        assert app.layout.status_panel is not None
    finally:
        app._on_close()
