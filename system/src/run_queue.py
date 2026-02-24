"""In-memory queue and history for phase-2 desktop execution flow."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, replace
from datetime import datetime, UTC
from pathlib import Path
from typing import Literal
from uuid import uuid4

from job_runner import RunRequest, RunResult


QueueStatus = Literal["pending", "running", "success", "failed", "cancelled", "timeout"]


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

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "return_code": self.return_code,
            "command": self.command,
            "request_mode": self.request.mode,
            "request_step": self.request.step,
            "request_article_id": self.request.article_id,
            "request_dry_run": self.request.dry_run,
            "request_force": self.request.force,
            "request_log_level": self.request.log_level,
            "request_timeout_minutes": self.request.timeout_minutes,
            "request_workspace_root": (
                str(self.request.workspace_root) if self.request.workspace_root else ""
            ),
            "request_project_root": (
                str(self.request.project_root) if self.request.project_root else ""
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> QueueItem:
        status = data.get("status", "failed")
        if status not in ("pending", "running", "success", "failed", "cancelled", "timeout"):
            status = "failed"

        mode = data.get("request_mode", "all")
        if mode not in ("all", "step"):
            mode = "all"

        step_raw = data.get("request_step")
        try:
            step = int(step_raw) if step_raw is not None else None
        except (TypeError, ValueError):
            step = None

        request = RunRequest(
            mode=mode,
            step=step,
            article_id=data.get("request_article_id", ""),
            dry_run=bool(data.get("request_dry_run", False)),
            force=bool(data.get("request_force", False)),
            log_level=data.get("request_log_level", "INFO"),
            timeout_minutes=float(data.get("request_timeout_minutes", 30.0)),
            workspace_root=(
                Path(data["request_workspace_root"])
                if data.get("request_workspace_root")
                else None
            ),
            project_root=(
                Path(data["request_project_root"])
                if data.get("request_project_root")
                else None
            ),
        )
        return cls(
            job_id=data["job_id"],
            request=request,
            status=status,
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            return_code=data.get("return_code"),
            command=data.get("command"),
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RunQueue:
    """Simple FIFO queue with run-state tracking."""

    def __init__(self) -> None:
        self._items: list[QueueItem] = []
        self._lock = threading.Lock()

    # -- private helpers (call only while holding self._lock) --

    def _running_item(self) -> QueueItem | None:
        for item in self._items:
            if item.status == "running":
                return item
        return None

    def _replace_item(self, job_id: str, **changes) -> QueueItem | None:
        for index, item in enumerate(self._items):
            if item.job_id != job_id:
                continue
            updated = replace(item, **changes)
            self._items[index] = updated
            return updated
        return None

    # -- public API (all guarded by self._lock) --

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for item in self._items if item.status == "pending")

    @property
    def running_item(self) -> QueueItem | None:
        with self._lock:
            return self._running_item()

    def snapshot(self) -> list[QueueItem]:
        with self._lock:
            return list(self._items)

    def enqueue(self, request: RunRequest) -> QueueItem:
        with self._lock:
            item = QueueItem(
                job_id=uuid4().hex[:8],
                request=request,
                status="pending",
                created_at=_now_iso(),
            )
            self._items.append(item)
            return item

    def start_next(self) -> QueueItem | None:
        with self._lock:
            if self._running_item() is not None:
                return None
            for item in self._items:
                if item.status != "pending":
                    continue
                return self._replace_item(
                    item.job_id, status="running", started_at=_now_iso()
                )
            return None

    def finish_running(self, result: RunResult) -> QueueItem | None:
        with self._lock:
            running = self._running_item()
            if running is None:
                return None
            status: QueueStatus = "success" if result.success else "failed"
            if result.return_code == -2:
                status = "timeout"
            return self._replace_item(
                running.job_id,
                status=status,
                finished_at=_now_iso(),
                return_code=result.return_code,
                command=list(result.command),
            )

    def cancel_running(self) -> QueueItem | None:
        with self._lock:
            running = self._running_item()
            if running is None:
                return None
            return self._replace_item(
                running.job_id,
                status="cancelled",
                finished_at=_now_iso(),
                return_code=-1,
            )

    def save_history(self, file_path: Path) -> None:
        """Save completed/failed/cancelled jobs to JSON file."""
        with self._lock:
            terminal = [
                item.to_dict()
                for item in self._items
                if item.status in ("success", "failed", "cancelled", "timeout")
            ]
        # Keep only last 100 entries
        terminal = terminal[-100:]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(terminal, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_history(self, file_path: Path) -> None:
        """Load job history from JSON file."""
        if not file_path.exists():
            return
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, list):
            return
        with self._lock:
            for entry in data:
                if isinstance(entry, dict):
                    try:
                        item = QueueItem.from_dict(entry)
                        self._items.append(item)
                    except (KeyError, TypeError):
                        continue
