"""Background job runner for GUI-triggered pipeline execution."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal


@dataclass(frozen=True)
class RunRequest:
    """One pipeline run request from the desktop UI."""

    mode: Literal["all", "step"]
    step: int | None
    article_id: str
    dry_run: bool
    force: bool
    log_level: str
    workspace_root: Path | None = None
    project_root: Path | None = None


@dataclass(frozen=True)
class RunResult:
    """Execution result metadata for one run."""

    success: bool
    return_code: int
    command: list[str]


def resolve_cli_runner(
    *, gui_executable: Path, default_main: Path
) -> tuple[Path, Path | None]:
    """Resolve runtime target for GUI launched from a packaged executable.

    Returns:
    - (`SAEC-OG-CLI.exe`, None) when sibling CLI executable exists
    - (gui_executable, None) fallback, relying on gui_main CLI dispatch
    """
    gui_executable = gui_executable.resolve()
    sibling_cli = gui_executable.with_name("SAEC-OG-CLI.exe")
    if sibling_cli.exists():
        return sibling_cli, None
    return gui_executable, None


def build_main_command(
    *, python_executable: str, main_script: Path | None, request: RunRequest
) -> list[str]:
    command = [python_executable]
    if main_script is not None:
        command.append(main_script.as_posix())
    if request.mode == "all":
        command.append("--all")
    else:
        if request.step is None:
            raise ValueError("step mode requires an explicit step value")
        command.extend(["--step", str(request.step)])

    article = request.article_id.strip()
    if article:
        command.extend(["--article", article])
    if request.dry_run:
        command.append("--dry-run")
    if request.force:
        command.append("--force")
    command.extend(["--log-level", (request.log_level or "INFO").upper()])
    return command


def build_runtime_env(
    *, base_env: dict[str, str], request: RunRequest
) -> dict[str, str]:
    env = dict(base_env)
    if request.project_root is not None:
        project_root = request.project_root.resolve()
        env["SAEC_EXTRACTION_PATH"] = str(project_root)
        env["SAEC_ARTICLES_PATH"] = str(
            (project_root / "inputs" / "articles").resolve()
        )
    return env


class PipelineJobRunner:
    """Threaded process runner that streams logs to callbacks."""

    def __init__(self, *, python_executable: str, main_script: Path | None) -> None:
        self.python_executable = python_executable
        self.main_script = main_script
        self._active_process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        with self._lock:
            proc = self._active_process
        return proc is not None and proc.poll() is None

    def cancel(self) -> None:
        with self._lock:
            proc = self._active_process
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()

    def run_async(
        self,
        request: RunRequest,
        *,
        on_output: Callable[[str], None],
        on_complete: Callable[[RunResult], None],
    ) -> threading.Thread:
        command = build_main_command(
            python_executable=self.python_executable,
            main_script=self.main_script,
            request=request,
        )
        env = build_runtime_env(base_env=dict(os.environ), request=request)

        def _run() -> None:
            proc: subprocess.Popen[str] | None = None
            try:
                proc = subprocess.Popen(
                    command,
                    cwd=(
                        str(self.main_script.parent)
                        if self.main_script is not None
                        else str(Path(self.python_executable).resolve().parent)
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                )
                with self._lock:
                    self._active_process = proc

                if proc.stdout is not None:
                    for line in proc.stdout:
                        on_output(line.rstrip("\n"))

                return_code = proc.wait()
                on_complete(
                    RunResult(
                        success=return_code == 0,
                        return_code=return_code,
                        command=command,
                    )
                )
            finally:
                with self._lock:
                    if self._active_process is proc:
                        self._active_process = None

        thread = threading.Thread(target=_run, name="saec-job-runner", daemon=True)
        thread.start()
        return thread
