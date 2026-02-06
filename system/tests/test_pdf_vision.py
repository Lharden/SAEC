from __future__ import annotations

from pdf_vision import _find_references_start_in_text


def test_find_references_start_in_text():
    text = "Intro\nMethods\nResults\nReferences\n[1] Author..."
    idx = _find_references_start_in_text(text)
    assert idx is not None
    assert text[idx:].startswith("References")
