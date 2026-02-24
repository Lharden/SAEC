"""Background job runner for GUI-triggered pipeline execution."""

from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
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
    timeout_minutes: float = 30.0
    workspace_root: Path | None = None
    project_root: Path | None = None
    articles_path: Path | None = None
    preset_name: str = ""


@dataclass(frozen=True)
class RunResult:
    """Execution result metadata for one run."""

    success: bool
    return_code: int
    command: list[str]


@dataclass(frozen=True)
class ProgressUpdate:
    """Progress snapshot parsed from runner stdout."""

    article_current: int | None = None
    article_total: int | None = None
    step_current: int | None = None
    step_total: int | None = None
    elapsed_seconds: float | None = None
    last_activity: str | None = None


_ARTICLE_PATTERNS = [
    re.compile(r"\[\s*Article\s+(\d+)\s*/\s*(\d+)\s*\]", re.IGNORECASE),
    re.compile(r"Processing article\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE),
]
_GENERIC_ARTICLE_PATTERN = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")
_STEP_PATTERNS = [
    re.compile(r"\[\s*Step\s+(\d+)\s*/\s*(\d+)\s*\]", re.IGNORECASE),
    re.compile(r"ETAPA\s+(\d+)\b", re.IGNORECASE),
]
# Patterns for real pipeline log output
_ART_ACTIVITY = re.compile(
    r"(ART_\d+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(OK|ERRO|USAGE)",
    re.IGNORECASE,
)
_TOTAL_ARTICLES = re.compile(r"Total de artigos:\s*(\d+)", re.IGNORECASE)
_DONE_ARTICLES = re.compile(r"Processados:\s*(\d+)", re.IGNORECASE)
_PENDING_ARTICLES = re.compile(r"Pendentes:\s*(\d+)", re.IGNORECASE)


class ProgressTracker:
    """Stateful tracker that accumulates progress across log lines."""

    def __init__(self) -> None:
        self._total: int | None = None
        self._pending: int | None = None
        self._done_initial: int = 0
        self._completed_arts: set[str] = set()
        self._last_activity: str = ""

    def parse(self, line: str, *, elapsed_seconds: float) -> ProgressUpdate | None:
        """Parse a log line and return a ProgressUpdate if progress changed."""
        article_current: int | None = None
        article_total: int | None = None
        step_current: int | None = None
        step_total: int | None = None
        last_activity: str | None = None

        # --- Parse total/pending/done from Step 1 output ---
        m = _TOTAL_ARTICLES.search(line)
        if m:
            self._total = int(m.group(1))

        m = _DONE_ARTICLES.search(line)
        if m:
            self._done_initial = int(m.group(1))

        m = _PENDING_ARTICLES.search(line)
        if m:
            self._pending = int(m.group(1))

        # --- Parse article activity (ART_XXX | provider | action | OK/ERRO) ---
        m = _ART_ACTIVITY.search(line)
        if m:
            art_id = m.group(1)
            provider = m.group(2)
            action = m.group(3)
            status = m.group(4).upper()
            if status == "USAGE":
                # USAGE lines are informational, don't count as completion
                last_activity = f"{art_id} — {action} ({provider})"
            elif action.lower() in ("extract_hybrid", "extract", "extract_local"):
                last_activity = f"{art_id} — {'✅' if status == 'OK' else '❌'} {action} ({provider})"
                self._completed_arts.add(art_id)
            elif action.lower() == "repair_yaml":
                last_activity = f"{art_id} — 🔧 repair ({provider})"
            else:
                last_activity = f"{art_id} — {action} ({provider})"

        # --- Parse ETAPA (step) markers ---
        for pattern in _STEP_PATTERNS:
            sm = pattern.search(line)
            if sm:
                step_current = int(sm.group(1))
                step_total = int(sm.group(2)) if sm.lastindex and sm.lastindex >= 2 else 5
                last_activity = f"Etapa {step_current}"
                break

        # --- Existing [Article X/Y] patterns ---
        for pattern in _ARTICLE_PATTERNS:
            am = pattern.search(line)
            if am:
                article_current = int(am.group(1))
                article_total = int(am.group(2))
                break

        # --- Compute article progress from accumulated state ---
        if article_current is None and self._total is not None:
            article_total = self._pending if self._pending else (self._total - self._done_initial)
            article_current = len(self._completed_arts)

        # Detect Falha na extracao as activity
        if "Falha na extracao" in line:
            last_activity = "❌ Falha na extração"

        if last_activity:
            self._last_activity = last_activity

        has_progress = any(v is not None for v in (article_current, article_total, step_current, step_total, last_activity))
        if not has_progress:
            return None

        return ProgressUpdate(
            article_current=article_current,
            article_total=article_total if article_total and article_total > 0 else None,
            step_current=step_current,
            step_total=step_total,
            elapsed_seconds=elapsed_seconds,
            last_activity=self._last_activity or None,
        )


def parse_progress_from_line(line: str, *, elapsed_seconds: float) -> ProgressUpdate | None:
    """Legacy stateless parser — kept for backward compatibility."""
    tracker = ProgressTracker()
    return tracker.parse(line, elapsed_seconds=elapsed_seconds)



def resolve_cli_runner(
    *, gui_executable: Path, default_main: Path
) -> tuple[Path, Path | None]:
    """Resolve runtime target for GUI launched from a packaged executable.

    Returns:
    - (`SAEC-CLI.exe`, None) when sibling CLI executable exists
    - (gui_executable, None) fallback, relying on gui_main CLI dispatch
    """
    gui_executable = gui_executable.resolve()
    sibling_cli = gui_executable.with_name("SAEC-CLI.exe")
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
    from presets import get_preset

    env = dict(base_env)

    runtime_base = request.project_root or Path.cwd()
    runtime_root = runtime_base / ".runtime"
    tmp_dir = runtime_root / "tmp"
    pip_cache_dir = runtime_root / "pip-cache"
    for path in (tmp_dir, pip_cache_dir):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Keep runner resilient even when runtime dir setup fails.
            continue
    env["SAEC_RUNTIME_ROOT"] = str(runtime_root.resolve())
    env["TEMP"] = str(tmp_dir.resolve())
    env["TMP"] = str(tmp_dir.resolve())
    env["PIP_CACHE_DIR"] = str(pip_cache_dir.resolve())

    if request.project_root is not None:
        project_root = request.project_root.resolve()
        env["SAEC_EXTRACTION_PATH"] = str(project_root)

        if request.articles_path is not None:
            env["SAEC_ARTICLES_PATH"] = str(request.articles_path.resolve())
        else:
            env["SAEC_ARTICLES_PATH"] = str(
                (project_root / "inputs" / "articles").resolve()
            )

    # Inject preset provider overrides into environment
    if request.preset_name:
        preset = get_preset(request.preset_name)
        for key, value in preset.provider_overrides.items():
            env[key] = value

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
        on_progress: Callable[[ProgressUpdate], None] | None = None,
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
                    bufsize=1,
                )
                with self._lock:
                    self._active_process = proc

                timeout_seconds = max(request.timeout_minutes * 60.0, 1.0)
                start_time = time.monotonic()
                done_sentinel = object()
                line_queue: queue.Queue[str | object] = queue.Queue()

                def _reader() -> None:
                    if proc is None or proc.stdout is None:
                        line_queue.put(done_sentinel)
                        return
                    for line in proc.stdout:
                        line_queue.put(line.rstrip("\n"))
                    line_queue.put(done_sentinel)

                reader = threading.Thread(target=_reader, name="saec-job-reader", daemon=True)
                reader.start()

                tracker = ProgressTracker()
                timed_out = False
                reader_done = False
                while True:
                    elapsed = time.monotonic() - start_time
                    if elapsed > timeout_seconds:
                        timed_out = True
                        on_output(
                            f"[TIMEOUT] Job exceeded {request.timeout_minutes:.0f} minute limit. Terminating..."
                        )
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        break

                    try:
                        payload = line_queue.get(timeout=0.1)
                    except queue.Empty:
                        payload = None

                    if payload is done_sentinel:
                        reader_done = True
                    elif isinstance(payload, str):
                        on_output(payload)
                        if on_progress is not None:
                            update = tracker.parse(payload, elapsed_seconds=elapsed)
                            if update is not None:
                                on_progress(update)

                    if reader_done and proc.poll() is not None and line_queue.empty():
                        break

                # Drain remaining lines produced right before process exit.
                while not line_queue.empty():
                    payload = line_queue.get_nowait()
                    if isinstance(payload, str):
                        elapsed = time.monotonic() - start_time
                        on_output(payload)
                        if on_progress is not None:
                            update = tracker.parse(payload, elapsed_seconds=elapsed)
                            if update is not None:
                                on_progress(update)

                if timed_out:
                    on_complete(
                        RunResult(
                            success=False,
                            return_code=-2,
                            command=command,
                        )
                    )
                    return

                return_code = proc.wait()
                on_complete(
                    RunResult(
                        success=return_code == 0,
                        return_code=return_code,
                        command=command,
                    )
                )
            except FileNotFoundError as exc:
                on_output(f"[RUNNER ERROR] Python interpreter not found: {exc}")
                on_complete(RunResult(success=False, return_code=-99, command=command))
            except PermissionError as exc:
                on_output(f"[RUNNER ERROR] Access denied to output folder: {exc}")
                on_complete(RunResult(success=False, return_code=-99, command=command))
            except Exception as exc:
                on_output(f"[RUNNER ERROR] Unexpected error. Check logs for details. {exc}")
                on_complete(RunResult(success=False, return_code=-99, command=command))
            finally:
                with self._lock:
                    if self._active_process is proc:
                        self._active_process = None

        thread = threading.Thread(target=_run, name="saec-job-runner", daemon=True)
        thread.start()
        return thread

