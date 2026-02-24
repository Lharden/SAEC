from __future__ import annotations

from job_runner import RunRequest
from gui.panel_queue import MAX_OUTPUT_LINES_PER_JOB, QueuePanel
from run_queue import QueueItem


class _FakeTree:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[object, ...]] = {}
        self._counter = 0

    def get_children(self) -> tuple[str, ...]:
        return tuple(self._rows.keys())

    def delete(self, row_id: str) -> None:
        self._rows.pop(row_id, None)

    def insert(
        self,
        _parent: str,
        _index: str,
        *,
        text: str,
        image,
        values: tuple[object, ...],
    ) -> str:
        del text, image
        self._counter += 1
        iid = f"iid-{self._counter}"
        self._rows[iid] = values
        return iid


def _request() -> RunRequest:
    return RunRequest(
        mode="all",
        step=None,
        article_id="ART_001",
        dry_run=False,
        force=False,
        log_level="INFO",
    )


def _queue_item(*, job_id: str) -> QueueItem:
    return QueueItem(
        job_id=job_id,
        request=_request(),
        status="success",
        created_at="2026-02-16T00:00:00+00:00",
        started_at="2026-02-16T00:00:01+00:00",
        finished_at="2026-02-16T00:00:10+00:00",
        return_code=0,
        command=["python", "main.py", "--all"],
    )


def test_record_output_caps_lines_per_job() -> None:
    panel = object.__new__(QueuePanel)
    panel._job_outputs = {}

    total_lines = MAX_OUTPUT_LINES_PER_JOB + 37
    for idx in range(total_lines):
        QueuePanel.record_output(panel, "job-a", f"line-{idx}")

    lines = panel._job_outputs["job-a"]
    assert len(lines) == MAX_OUTPUT_LINES_PER_JOB
    assert lines[0] == "line-37"
    assert lines[-1] == f"line-{total_lines - 1}"


def test_refresh_removes_stale_job_outputs() -> None:
    panel = object.__new__(QueuePanel)
    panel._tree = _FakeTree()
    panel._job_meta = {}
    panel._job_outputs = {
        "active-job": ["active-line"],
        "old-job": ["stale-line"],
    }
    panel._status_icons = {
        "pending": None,
        "running": None,
        "success": None,
        "failed": None,
        "cancelled": None,
        "timeout": None,
    }

    QueuePanel.refresh(panel, [_queue_item(job_id="active-job")])

    assert "old-job" not in panel._job_outputs
    assert panel._job_outputs["active-job"] == ["active-line"]
    assert len(panel._job_meta) == 1
