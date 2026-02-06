from __future__ import annotations

from pathlib import Path

import config


def test_paths_uses_articles_override_when_set(monkeypatch, tmp_path: Path) -> None:
    articles = tmp_path / "my-articles"
    monkeypatch.setenv("SAEC_ARTICLES_PATH", str(articles))

    paths = config.Paths()

    assert paths.ARTICLES == articles.resolve()


def test_paths_uses_extraction_override_when_set(monkeypatch, tmp_path: Path) -> None:
    extraction = tmp_path / "my-extraction"
    monkeypatch.setenv("SAEC_EXTRACTION_PATH", str(extraction))

    paths = config.Paths()

    assert paths.EXTRACTION == extraction.resolve()
    assert paths.OUTPUTS == extraction.resolve() / "outputs"
