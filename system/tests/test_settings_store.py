from __future__ import annotations

from pathlib import Path

from settings_store import SettingsStore


def test_load_returns_defaults_when_file_does_not_exist(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    data = store.load()

    assert data["recent_workspaces"] == []
    assert data["last_workspace"] == ""
    assert data["last_project_by_workspace"] == {}
    assert data["selected_preset"] == "pilot"


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    payload = {
        "recent_workspaces": ["C:/ws-a"],
        "last_workspace": "C:/ws-a",
        "last_project_by_workspace": {"C:/ws-a": "alpha"},
        "selected_preset": "batch",
    }

    store.save(payload)
    loaded = store.load()

    assert loaded == payload


def test_add_recent_workspace_deduplicates_and_keeps_latest_first(
    tmp_path: Path,
) -> None:
    store = SettingsStore(tmp_path)
    store.add_recent_workspace(Path("C:/ws-a"))
    store.add_recent_workspace(Path("C:/ws-b"))
    store.add_recent_workspace(Path("C:/ws-a"))

    data = store.load()
    assert data["recent_workspaces"][:2] == ["C:\\ws-a", "C:\\ws-b"]
