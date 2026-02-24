from __future__ import annotations

from pathlib import Path

from health_check import check_api_keys, check_disk_space


def test_check_api_keys_warns_when_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")

    result = check_api_keys(env_path)

    assert result.status == "WARN"


def test_check_api_keys_ok_when_present(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=abc\n", encoding="utf-8")

    result = check_api_keys(env_path)

    assert result.status == "OK"


def test_check_disk_space_returns_status(tmp_path: Path) -> None:
    result = check_disk_space(tmp_path, min_free_gb=0.0001)

    assert result.status in {"OK", "WARN"}
