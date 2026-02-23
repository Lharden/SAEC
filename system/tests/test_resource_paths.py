from __future__ import annotations

import sys
from pathlib import Path

import resource_paths


def test_get_resource_path_in_dev_mode(monkeypatch) -> None:
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    out = resource_paths.get_resource_path("gui/resources/saec.ico")

    assert isinstance(out, Path)
    assert str(out).endswith(str(Path("system") / "gui" / "resources" / "saec.ico"))


def test_get_resource_path_in_bundle_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    out = resource_paths.get_resource_path("x/y.dat")

    assert out == (tmp_path / "x" / "y.dat").resolve()
