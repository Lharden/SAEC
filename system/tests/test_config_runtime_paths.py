import sys

import config


def test_detect_project_root_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SAEC_PROJECT_ROOT", str(tmp_path))
    detected = config._detect_project_root()
    assert detected == tmp_path.resolve()


def test_detect_project_root_frozen_prefers_exe_dir(monkeypatch, tmp_path):
    root = tmp_path / "project"
    (root / "system").mkdir(parents=True)
    (root / "Extraction").mkdir(parents=True)
    exe_path = root / "SAEC.exe"
    exe_path.write_text("", encoding="utf-8")

    monkeypatch.delenv("SAEC_PROJECT_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path), raising=False)

    detected = config._detect_project_root()
    assert detected == root.resolve()


def test_detect_project_root_frozen_uses_exe_parent(monkeypatch, tmp_path):
    root = tmp_path / "project"
    dist_dir = root / "system" / "dist"
    dist_dir.mkdir(parents=True)
    (root / "Extraction").mkdir(parents=True)
    exe_path = dist_dir / "SAEC.exe"
    exe_path.write_text("", encoding="utf-8")

    monkeypatch.delenv("SAEC_PROJECT_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path), raising=False)

    detected = config._detect_project_root()
    assert detected == root.resolve()

