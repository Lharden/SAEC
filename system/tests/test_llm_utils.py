from __future__ import annotations

from pathlib import Path

from llm_utils import extract_yaml_from_response


FIXTURES = Path(__file__).parent / "fixtures" / "llm_responses"


def test_extract_yaml_clean_response():
    text = (FIXTURES / "clean_response.txt").read_text(encoding="utf-8")
    yaml_content = extract_yaml_from_response(text)
    assert yaml_content.strip().startswith("---")
    assert "ArtigoID:" in yaml_content
    assert yaml_content.strip().endswith("---")


def test_extract_yaml_markdown_wrapped():
    text = (FIXTURES / "markdown_wrapped.txt").read_text(encoding="utf-8")
    yaml_content = extract_yaml_from_response(text)
    assert yaml_content.strip().startswith("---")
    assert "ArtigoID:" in yaml_content
