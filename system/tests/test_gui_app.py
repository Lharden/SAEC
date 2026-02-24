from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gui.pipeline_controller import PipelineController
from gui.project_manager import ProjectManager


class _StatusVar:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _FakeLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message: str, *args: object) -> None:
        if args:
            self.lines.append(message % args)
        else:
            self.lines.append(message)


class _FakeQueuePanel:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def record_output(self, job_id: str, line: str) -> None:
        self.records.append((job_id, line))


def test_write_env_file_preserves_comments_order_and_newline_behavior(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# Existing config\n"
        "API_KEY=old-value\n"
        "\n"
        "# Keep this comment\n"
        "UNCHANGED=1",
        encoding="utf-8",
    )

    ProjectManager.write_env_to_path(
        env_path,
        {"API_KEY": "new-value", "NEW_TOKEN": "abc123"},
    )

    assert env_path.read_text(encoding="utf-8") == (
        "# Existing config\n"
        "API_KEY=new-value\n"
        "\n"
        "# Keep this comment\n"
        "UNCHANGED=1\n"
        "NEW_TOKEN=abc123\n"
        "OLLAMA_ENABLED=true"
    )


def test_write_env_file_preserves_existing_trailing_newline(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("KEY=value\n", encoding="utf-8")

    ProjectManager.write_env_to_path(env_path, {})

    content = env_path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert "KEY=value\n" in content
    assert "OLLAMA_ENABLED=true\n" in content


def test_write_env_file_allows_clearing_existing_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=old\n", encoding="utf-8")

    ProjectManager.write_env_to_path(
        env_path,
        {"OPENAI_API_KEY": ""},
    )

    content = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=\n" in content


def test_on_runner_output_uses_eager_capture_defaults() -> None:
    queue_panel = _FakeQueuePanel()
    logger = _FakeLogger()
    callbacks: list[object] = []

    def _after(_delay_ms: int, callback):
        callbacks.append(callback)
        return "after-id"

    fake_app = SimpleNamespace(
        _running_job_id="job-001",
        layout=SimpleNamespace(queue_panel=queue_panel),
        after=_after,
    )

    ctrl = PipelineController.__new__(PipelineController)
    ctrl._app = fake_app  # type: ignore[assignment]
    ctrl._logger = logger  # type: ignore[assignment]
    ctrl.on_runner_output("hello world")

    assert len(callbacks) == 1
    callback = callbacks[0]
    assert getattr(callback, "__defaults__", None) == ("job-001", "hello world")

    fake_app._running_job_id = "job-999"
    callback()

    assert queue_panel.records == [("job-001", "hello world")]
    assert logger.lines == ["hello world"]
