from __future__ import annotations

from job_runner import RunRequest, RunResult
from run_queue import RunQueue


def _request(article: str = "") -> RunRequest:
    return RunRequest(
        mode="all",
        step=None,
        article_id=article,
        dry_run=False,
        force=False,
        log_level="INFO",
    )


def test_queue_enqueues_items_as_pending() -> None:
    queue = RunQueue()

    item = queue.enqueue(_request("ART_001"))

    assert item.status == "pending"
    assert queue.pending_count == 1
    assert queue.running_item is None


def test_queue_starts_oldest_pending_and_tracks_running() -> None:
    queue = RunQueue()
    first = queue.enqueue(_request("ART_001"))
    second = queue.enqueue(_request("ART_002"))

    started = queue.start_next()

    assert started is not None
    assert started.job_id == first.job_id
    assert started.status == "running"
    assert queue.running_item is not None
    assert queue.running_item.job_id == first.job_id
    assert queue.pending_count == 1
    assert queue.snapshot()[1].job_id == second.job_id


def test_queue_marks_completion_and_records_return_code() -> None:
    queue = RunQueue()
    item = queue.enqueue(_request("ART_010"))
    queue.start_next()

    result = RunResult(success=True, return_code=0, command=["x"])
    done = queue.finish_running(result)

    assert done is not None
    assert done.job_id == item.job_id
    assert done.status == "success"
    assert done.return_code == 0
    assert queue.running_item is None


def test_queue_cancel_running_marks_cancelled() -> None:
    queue = RunQueue()
    queue.enqueue(_request("ART_099"))
    queue.start_next()

    cancelled = queue.cancel_running()

    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert queue.running_item is None
