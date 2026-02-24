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
    active_profile_id: str = ""
    active_profile_version: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
        }
        if self.active_profile_id:
            payload["active_profile_id"] = self.active_profile_id
        if self.active_profile_version:
            payload["active_profile_version"] = self.active_profile_version
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, str], root: Path) -> "ProjectSummary":
        return cls(
            project_id=str(data.get("project_id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            root=root,
            created_at=str(data.get("created_at", "")).strip(),
            active_profile_id=str(data.get("active_profile_id", "")).strip(),
            active_profile_version=str(data.get("active_profile_version", "")).strip(),
        )
