"""In-memory queue and history for phase-2 desktop execution flow."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, UTC
from typing import Literal
from uuid import uuid4

from job_runner import RunRequest, RunResult


QueueStatus = Literal["pending", "running", "success", "failed", "cancelled"]


@dataclass(frozen=True)
class QueueItem:
    job_id: str
    request: RunRequest
    status: QueueStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    return_code: int | None = None
    command: list[str] | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RunQueue:
    """Simple FIFO queue with run-state tracking."""

    def __init__(self) -> None:
        self._items: list[QueueItem] = []

    @property
    def pending_count(self) -> int:
        return sum(1 for item in self._items if item.status == "pending")

    @property
    def running_item(self) -> QueueItem | None:
        for item in self._items:
            if item.status == "running":
                return item
        return None

    def snapshot(self) -> list[QueueItem]:
        return list(self._items)

    def enqueue(self, request: RunRequest) -> QueueItem:
        item = QueueItem(
            job_id=uuid4().hex[:8],
            request=request,
            status="pending",
            created_at=_now_iso(),
        )
        self._items.append(item)
        return item

    def _replace_item(self, job_id: str, **changes) -> QueueItem | None:
        for index, item in enumerate(self._items):
            if item.job_id != job_id:
                continue
            updated = replace(item, **changes)
            self._items[index] = updated
            return updated
        return None

    def start_next(self) -> QueueItem | None:
        if self.running_item is not None:
            return None
        for item in self._items:
            if item.status != "pending":
                continue
            return self._replace_item(
                item.job_id, status="running", started_at=_now_iso()
            )
        return None

    def finish_running(self, result: RunResult) -> QueueItem | None:
        running = self.running_item
        if running is None:
            return None
        status: QueueStatus = "success" if result.success else "failed"
        return self._replace_item(
            running.job_id,
            status=status,
            finished_at=_now_iso(),
            return_code=result.return_code,
            command=list(result.command),
        )

    def cancel_running(self) -> QueueItem | None:
        running = self.running_item
        if running is None:
            return None
        return self._replace_item(
            running.job_id,
            status="cancelled",
            finished_at=_now_iso(),
            return_code=-1,
        )
