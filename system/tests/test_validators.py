from __future__ import annotations

from pathlib import Path

from validators import validate_yaml


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_valid_extraction_yaml():
    content = _load("valid_extraction.yaml")
    result = validate_yaml(content)
    assert result.is_valid, result.errors


def test_invalid_tipo_risco():
    content = _load("invalid_tipo_risco.yaml")
    result = validate_yaml(content)
    assert not result.is_valid
    assert any("[R1]" in e for e in result.errors)


def test_invalid_quotes_count():
    content = _load("invalid_quotes.yaml")
    result = validate_yaml(content)
    assert not result.is_valid
