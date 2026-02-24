from __future__ import annotations

from pathlib import Path
import sys
import types

SYSTEM_ROOT = Path(__file__).resolve().parents[1]
if str(SYSTEM_ROOT) not in sys.path:
    sys.path.insert(0, str(SYSTEM_ROOT))

import gui_main


def test_main_dispatches_pipeline_cli_flags(monkeypatch) -> None:
    pipeline_module = types.ModuleType("main")
    calls: list[str] = []

    def _pipeline_main() -> int:
        calls.append("pipeline-main")
        return 7

    pipeline_module.main = _pipeline_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "main", pipeline_module)
    monkeypatch.setattr(gui_main, "_bootstrap_paths", lambda: None)
    monkeypatch.setattr(sys, "argv", ["gui_main.py", "--status"])

    assert gui_main.main() == 7
    assert calls == ["pipeline-main"]


def test_main_shows_splash_before_app_creation(monkeypatch) -> None:
    events: list[str] = []

    class _FakeApp:
        def __init__(self) -> None:
            events.append("app-init")

        def mainloop(self) -> None:
            events.append("mainloop")

    app_module = types.ModuleType("gui.app")
    app_module.SAECWin98App = _FakeApp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gui.app", app_module)

    monkeypatch.setattr(gui_main, "_bootstrap_paths", lambda: None)
    monkeypatch.setattr(
        gui_main,
        "_show_bootstrap_splash",
        lambda **_kwargs: events.append("splash"),
    )
    monkeypatch.setattr(sys, "argv", ["gui_main.py"])

    assert gui_main.main() == 0
    assert events == ["splash", "app-init", "mainloop"]
