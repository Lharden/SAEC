from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters import rag_store as mod
from adapters.rag_store import Chunk, RAGConfig, RAGError, RAGStore, SearchResult


def test_chunk_text_generates_multiple_chunks() -> None:
    text = ("abcde " * 200).strip()
    chunks = mod.chunk_text(text, chunk_size=120, chunk_overlap=20)
    assert len(chunks) > 1
    assert chunks[0][1] == 0
    assert chunks[0][2] <= 120


def test_chunk_text_rejects_invalid_params() -> None:
    with pytest.raises(ValueError, match="chunk_size must be > 0"):
        mod.chunk_text("abc", chunk_size=0, chunk_overlap=0)
    with pytest.raises(ValueError, match="chunk_overlap must be >= 0"):
        mod.chunk_text("abc", chunk_size=10, chunk_overlap=-1)
    with pytest.raises(ValueError, match="chunk_overlap must be < chunk_size"):
        mod.chunk_text("abc", chunk_size=10, chunk_overlap=10)


def test_chunk_by_sections_splits_markdown_headers() -> None:
    text = "# Intro\nalpha\n\n# Methods\nbeta"
    chunks = mod.chunk_by_sections(text, max_chunk_size=100)
    assert len(chunks) == 2
    assert chunks[0][1] == "Intro"
    assert chunks[1][1] == "Methods"


def test_search_converts_collection_results(monkeypatch) -> None:
    store = RAGStore(RAGConfig())
    monkeypatch.setattr(store, "_ensure_initialized", lambda: None)
    monkeypatch.setattr(store, "_get_embedding", lambda _query: [0.1, 0.2])
    store._collection = SimpleNamespace(
        query=lambda **_: {
            "ids": [["id_1"]],
            "documents": [["chunk text"]],
            "metadatas": [[{"artigo_id": "ART_001", "page_number": 3, "section": "Intro"}]],
            "distances": [[0.2]],
        }
    )

    out = store.search("query", top_k=1)

    assert len(out) == 1
    assert out[0].chunk.id == "id_1"
    assert out[0].score == pytest.approx(0.8)


def test_search_raises_rag_error_on_failure(monkeypatch) -> None:
    store = RAGStore(RAGConfig())
    monkeypatch.setattr(store, "_ensure_initialized", lambda: None)
    monkeypatch.setattr(store, "_get_embedding", lambda _query: [0.1, 0.2])
    store._collection = SimpleNamespace(query=lambda **_: (_ for _ in ()).throw(RuntimeError("db down")))

    with pytest.raises(RAGError, match="Search failed"):
        store.search("query")


def test_get_context_for_cimo_formats_results(monkeypatch) -> None:
    store = RAGStore(RAGConfig())
    dummy = SearchResult(
        chunk=Chunk(
            id="c1",
            text="relevant chunk",
            artigo_id="ART_001",
            page_number=1,
            section="Outcome",
        ),
        score=0.9,
        distance=0.1,
    )
    monkeypatch.setattr(store, "search", lambda *args, **kwargs: [dummy])

    context = store.get_context_for_cimo("ART_001", "outcome", top_k=1)

    assert "[Trecho 1 - Outcome]" in context
    assert "relevant chunk" in context


def test_get_default_store_is_singleton(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mod, "_default_store", None)

    first = mod.get_default_store(tmp_path / "idx-a")
    second = mod.get_default_store(tmp_path / "idx-b")

    assert first is second
    assert first.config.persist_dir == tmp_path / "idx-a"
