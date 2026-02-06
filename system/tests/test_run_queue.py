from __future__ import annotations

import threading

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


def test_concurrent_enqueue_from_multiple_threads() -> None:
    queue = RunQueue()
    num_threads = 10
    items_per_thread = 10
    barrier = threading.Barrier(num_threads)

    def _enqueue_batch(thread_idx: int) -> None:
        barrier.wait()
        for i in range(items_per_thread):
            queue.enqueue(_request(f"T{thread_idx}_ART_{i:03d}"))

    threads = [
        threading.Thread(target=_enqueue_batch, args=(t,))
        for t in range(num_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(queue.snapshot()) == num_threads * items_per_thread
    assert queue.pending_count == num_threads * items_per_thread


def test_snapshot_returns_consistent_copy() -> None:
    queue = RunQueue()
    queue.enqueue(_request("ART_SNAP_1"))
    queue.enqueue(_request("ART_SNAP_2"))

    snap = queue.snapshot()

    # Mutating the snapshot list must not affect the queue
    snap.pop()
    snap.clear()

    assert len(queue.snapshot()) == 2
    assert queue.pending_count == 2
