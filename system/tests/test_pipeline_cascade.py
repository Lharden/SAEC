from __future__ import annotations

from types import SimpleNamespace

import pytest

import pipeline_cascade as mod


def _validation(*, is_valid: bool, errors: list[str] | None = None, warnings: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(is_valid=is_valid, errors=errors or [], warnings=warnings or [])


def test_build_api_content_blocks_truncates_text() -> None:
    blocks = mod._build_api_content_blocks("x" * 120000)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert len(blocks[0]["text"]) == 100000


def test_extract_yaml_block_handles_code_fences() -> None:
    content = "prefix\n```yaml\nArtigoID: ART_001\n```\nsuffix"
    assert mod._extract_yaml_block(content) == "ArtigoID: ART_001"


def test_estimate_api_cost_by_provider() -> None:
    assert mod._estimate_api_cost("anthropic", 1000) == pytest.approx(0.009)
    assert mod._estimate_api_cost("openai", 1000) == pytest.approx(0.01)


def test_estimate_confidence_bounds_and_factors() -> None:
    empty = mod._estimate_confidence("", None)
    good_yaml = "ArtigoID: A\nClasseIA: B\nMecanismo_Estruturado: X\nQuotes: []\nProblemaNegócio_Contexto: Y\nIntervenção_Descrição: Z\nResultadoTipo: T\nNívelEvidência: E\n"
    good = mod._estimate_confidence(good_yaml * 20, _validation(is_valid=True))
    bad = mod._estimate_confidence("ArtigoID: A", _validation(is_valid=False, errors=["e1", "e2"], warnings=["w1"]))
    assert empty == 0.0
    assert 0.0 <= bad <= 1.0
    assert good > bad


def test_select_best_result_returns_hybrid_when_local_tokens_used() -> None:
    metrics = mod.CascadeMetrics(local_tokens=10)
    src = mod._select_best_result(
        mod.LocalAttemptResult(),
        mod.ExtractionSource.API_OPENAI,
        metrics,
    )
    assert src == mod.ExtractionSource.HYBRID


def test_extract_cascade_api_only_uses_api_branch(monkeypatch) -> None:
    expected = mod.CascadeResult(
        yaml_content="ok",
        source=mod.ExtractionSource.API_OPENAI,
        confidence=0.8,
        validation=None,
        metrics=mod.CascadeMetrics(),
    )
    monkeypatch.setattr(mod, "_try_api_only_extraction", lambda *args, **kwargs: expected)

    out = mod.extract_cascade("ART_001", "text", "{TEXT}", strategy="api_only")

    assert out is expected


def test_extract_cascade_returns_local_when_accepted(monkeypatch) -> None:
    local = mod.LocalAttemptResult(
        yaml_content="yaml-local",
        validation=_validation(is_valid=True),
        confidence=0.95,
        source=mod.ExtractionSource.LOCAL_OLLAMA,
        accepted=True,
    )
    monkeypatch.setattr(mod, "_try_local_extraction", lambda *args, **kwargs: local)

    out = mod.extract_cascade("ART_001", "text", "{TEXT}", strategy="local_first")

    assert out.yaml_content == "yaml-local"
    assert out.source == mod.ExtractionSource.LOCAL_OLLAMA
    assert out.success is True


def test_extract_cascade_local_only_uses_confidence_threshold(monkeypatch) -> None:
    local = mod.LocalAttemptResult(
        yaml_content="yaml-partial",
        validation=_validation(is_valid=False, errors=["e"]),
        confidence=0.6,
        source=mod.ExtractionSource.LOCAL_OLLAMA,
        accepted=False,
    )
    monkeypatch.setattr(mod, "_try_local_extraction", lambda *args, **kwargs: local)

    out = mod.extract_cascade("ART_001", "text", "{TEXT}", strategy="local_only")

    assert out.yaml_content == "yaml-partial"
    assert out.success is True


def test_resolve_api_provider_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(mod.llm_config, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(mod.llm_config, "ANTHROPIC_API_KEY", "real-key", raising=False)
    monkeypatch.setattr(mod, "_is_placeholder_api_key", lambda value: not bool(str(value).strip()))

    out = mod._resolve_api_provider("openai")
    assert out == "anthropic"
