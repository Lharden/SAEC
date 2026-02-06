from __future__ import annotations

from pathlib import Path

from job_runner import (
    RunRequest,
    build_main_command,
    build_runtime_env,
    resolve_cli_runner,
)


def test_build_main_command_for_all_with_flags() -> None:
    request = RunRequest(
        mode="all",
        step=None,
        article_id="ART_001",
        dry_run=True,
        force=True,
        log_level="DEBUG",
    )

    command = build_main_command(
        python_executable="python",
        main_script=Path("system/main.py"),
        request=request,
    )

    assert command == [
        "python",
        "system/main.py",
        "--all",
        "--article",
        "ART_001",
        "--dry-run",
        "--force",
        "--log-level",
        "DEBUG",
    ]


def test_build_main_command_for_specific_step() -> None:
    request = RunRequest(
        mode="step",
        step=3,
        article_id="",
        dry_run=False,
        force=False,
        log_level="INFO",
    )

    command = build_main_command(
        python_executable="py",
        main_script=Path("main.py"),
        request=request,
    )

    assert command == ["py", "main.py", "--step", "3", "--log-level", "INFO"]


def test_build_main_command_for_packaged_cli_exe_without_script() -> None:
    request = RunRequest(
        mode="all",
        step=None,
        article_id="",
        dry_run=False,
        force=False,
        log_level="INFO",
    )

    command = build_main_command(
        python_executable="dist/SAEC-OG-CLI.exe",
        main_script=None,
        request=request,
    )

    assert command == ["dist/SAEC-OG-CLI.exe", "--all", "--log-level", "INFO"]


def test_resolve_cli_runner_prefers_sibling_cli_exe(tmp_path: Path) -> None:
    gui_exe = tmp_path / "SAEC-OG.exe"
    gui_exe.write_text("", encoding="utf-8")
    cli_exe = tmp_path / "SAEC-OG-CLI.exe"
    cli_exe.write_text("", encoding="utf-8")

    runner, script = resolve_cli_runner(
        gui_executable=gui_exe, default_main=tmp_path / "main.py"
    )

    assert runner == cli_exe
    assert script is None


def test_resolve_cli_runner_falls_back_to_gui_exe_without_main_script(
    tmp_path: Path,
) -> None:
    gui_exe = tmp_path / "SAEC-OG.exe"
    gui_exe.write_text("", encoding="utf-8")

    runner, script = resolve_cli_runner(
        gui_executable=gui_exe,
        default_main=tmp_path / "main.py",
    )

    assert runner == gui_exe
    assert script is None


def test_build_runtime_env_injects_project_overrides(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "projects" / "alpha"
    articles_path = project_root / "inputs" / "articles"

    request = RunRequest(
        mode="all",
        step=None,
        article_id="",
        dry_run=False,
        force=False,
        log_level="INFO",
        workspace_root=workspace_root,
        project_root=project_root,
    )

    env = build_runtime_env(base_env={"A": "1"}, request=request)

    assert env["A"] == "1"
    assert env["SAEC_ARTICLES_PATH"] == str(articles_path.resolve())
    assert env["SAEC_EXTRACTION_PATH"] == str(project_root.resolve())
