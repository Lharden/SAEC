"""Project domain models for workspace-aware UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectSummary:
    """Public metadata for one SAEC project."""

    project_id: str
    name: str
    root: Path
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str], root: Path) -> "ProjectSummary":
        return cls(
            project_id=str(data.get("project_id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            root=root,
            created_at=str(data.get("created_at", "")).strip(),
        )
