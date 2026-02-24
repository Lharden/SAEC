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
    assert data["window_geometry"] == ""
    assert data["active_tab"] == 0
    assert data["main_sash_position"] == 320
    assert data["notify_on_completion"] is True
    assert data["setup_completed"] is False


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    payload = {
        "recent_workspaces": ["C:/ws-a"],
        "last_workspace": "C:/ws-a",
        "last_project_by_workspace": {"C:/ws-a": "alpha"},
        "articles_override_by_project": {},
        "selected_preset": "batch",
        "window_geometry": "",
        "active_tab": 0,
        "main_sash_position": 400,
        "notify_on_completion": True,
        "setup_completed": True,
    }

    store.save(payload)
    loaded = store.load()

    assert loaded == payload


def test_save_and_get_window_state(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.save_window_state(
        geometry="1200x800+100+50", active_tab=2, main_sash_position=420
    )

    state = store.get_window_state()
    assert state["geometry"] == "1200x800+100+50"
    assert state["active_tab"] == 2
    assert state["main_sash_position"] == 420


def test_get_window_state_defaults(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    state = store.get_window_state()
    assert state["geometry"] == ""
    assert state["active_tab"] == 0
    assert state["main_sash_position"] == 320


def test_normalize_invalid_window_state_types(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    # Save with intentionally wrong types
    payload = {
        "window_geometry": 123,
        "active_tab": "not_an_int",
    }
    store.save(payload)
    loaded = store.load()
    assert loaded["window_geometry"] == ""
    assert loaded["active_tab"] == 0


def test_add_recent_workspace_deduplicates_and_keeps_latest_first(
    tmp_path: Path,
) -> None:
    store = SettingsStore(tmp_path)
    store.add_recent_workspace(Path("C:/ws-a"))
    store.add_recent_workspace(Path("C:/ws-b"))
    store.add_recent_workspace(Path("C:/ws-a"))

    data = store.load()
    assert data["recent_workspaces"][:2] == ["C:\\ws-a", "C:\\ws-b"]
