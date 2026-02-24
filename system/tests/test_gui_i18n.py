"""Verify i18n module: coverage and correctness."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui.i18n import (
    t,
    set_language,
    get_language,
    all_keys,
    available_languages,
    _STRINGS,
)


def test_all_keys_have_both_languages() -> None:
    """Every key must have both pt-BR and en-UK entries."""
    missing_pt: list[str] = []
    missing_en: list[str] = []
    for key, entry in _STRINGS.items():
        if not entry.get("pt-BR"):
            missing_pt.append(key)
        if not entry.get("en-UK"):
            missing_en.append(key)
    assert not missing_pt, f"Missing pt-BR: {missing_pt}"
    assert not missing_en, f"Missing en-UK: {missing_en}"


def test_no_empty_translations() -> None:
    """No translation string should be empty."""
    for key, entry in _STRINGS.items():
        for lang, text in entry.items():
            assert text.strip(), f"Empty translation: {key} [{lang}]"


def test_t_returns_correct_language() -> None:
    set_language("pt-BR")
    assert t("menu.file") == "Arquivo"
    set_language("en-UK")
    assert t("menu.file") == "File"


def test_t_format_placeholders() -> None:
    set_language("pt-BR")
    result = t("status.article_n_of_m", current=3, total=10)
    assert "3" in result and "10" in result

    set_language("en-UK")
    result = t("status.article_n_of_m", current=3, total=10)
    assert result == "Article 3/10"


def test_t_unknown_key_returns_key() -> None:
    assert t("nonexistent.key") == "nonexistent.key"


def test_set_language_invalid_is_noop() -> None:
    set_language("pt-BR")
    set_language("invalid")
    assert get_language() == "pt-BR"


def test_available_languages_has_both() -> None:
    langs = available_languages()
    codes = [code for code, _label in langs]
    assert "pt-BR" in codes
    assert "en-UK" in codes


def test_minimum_key_count() -> None:
    """We expect at least 100 keys for adequate coverage."""
    keys = all_keys()
    assert len(keys) >= 100, f"Only {len(keys)} keys (expected ≥100)"
