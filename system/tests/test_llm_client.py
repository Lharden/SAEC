from __future__ import annotations

from types import SimpleNamespace

import pytest

import llm_client as mod


class _DummyConfig:
    ANTHROPIC_API_KEY = ""
    OPENAI_API_KEY = ""
    OLLAMA_ENABLED = False
    OLLAMA_BASE_URL = "http://localhost:11434/v1"
    RETRY_MAX_RETRIES = 1
    RETRY_BASE_DELAY = 0.01
    RETRY_MAX_DELAY = 0.1
    RETRY_JITTER = 0.0
    RETRY_MAX_ELAPSED = 1.0
    OLLAMA_MODEL_CLOUD = "model-a"
    OLLAMA_MODEL_CLOUD_FALLBACK = "model-b"
    OLLAMA_MODEL_VISION = "vision-model"
    OPENAI_MODEL = "gpt-test"
    ANTHROPIC_MODEL = "claude-test"
    PROMPT_CACHE_ENABLED = False
    ANTHROPIC_CACHE_TTL = "5m"
    PROMPT_CACHE_KEY = ""
    PROMPT_CACHE_RETENTION = ""

    @staticmethod
    def get_httpx_timeout() -> float:
        return 10.0


def _client() -> mod.LLMClient:
    ctx = SimpleNamespace(llm_config=_DummyConfig(), paths=SimpleNamespace())
    return mod.LLMClient(ctx)


def test_has_image_blocks() -> None:
    assert mod.LLMClient._has_image_blocks([{"type": "image_url"}]) is True
    assert mod.LLMClient._has_image_blocks([{"type": "text"}]) is False


def test_get_ollama_hybrid_model_switches_by_content() -> None:
    client = _client()
    assert client._get_ollama_hybrid_model([{"type": "text"}]) == "model-a"
    assert client._get_ollama_hybrid_model([{"type": "image_url"}]) == "vision-model"


def test_iter_ollama_repair_models_deduplicates() -> None:
    client = _client()
    client.llm_config.OLLAMA_MODEL_CLOUD = "m1"
    client.llm_config.OLLAMA_MODEL_CLOUD_FALLBACK = "m1"
    assert client._iter_ollama_repair_models() == ["m1"]


def test_check_provider_raises_when_provider_unavailable() -> None:
    client = _client()
    with pytest.raises(ValueError, match="anthropic"):
        client._check_provider("anthropic")
    with pytest.raises(ValueError, match="openai-compatible"):
        client._check_provider("openai")
    with pytest.raises(ValueError, match="openai-compatible"):
        client._check_provider("ollama")


def test_call_with_retry_logs_success(monkeypatch) -> None:
    client = _client()
    log_calls: list[dict[str, object]] = []
    monkeypatch.setattr(mod, "retry_with_backoff", lambda **_: (lambda fn: fn))
    monkeypatch.setattr(mod, "log_llm_call", lambda **kwargs: log_calls.append(kwargs))

    out = client._call_with_retry(lambda: "ok", provider="openai", action="extract")

    assert out == "ok"
    assert log_calls[-1]["success"] is True


def test_call_with_retry_logs_failure(monkeypatch) -> None:
    client = _client()
    log_calls: list[dict[str, object]] = []
    monkeypatch.setattr(mod, "retry_with_backoff", lambda **_: (lambda fn: fn))
    monkeypatch.setattr(mod, "log_llm_call", lambda **kwargs: log_calls.append(kwargs))

    with pytest.raises(RuntimeError, match="boom"):
        client._call_with_retry(
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            provider="openai",
            action="extract",
        )

    assert log_calls[-1]["success"] is False


def test_repair_ollama_falls_back_to_openai(monkeypatch) -> None:
    client = _client()
    client.ollama = object()
    client.openai = object()
    monkeypatch.setattr(
        client,
        "_call_with_retry",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fail")),
    )
    monkeypatch.setattr(client, "_repair_openai", lambda *args, **kwargs: "fixed-yaml")

    out = client._repair_ollama("prompt", "system", 4000)

    assert out == "fixed-yaml"


def test_repair_ollama_raises_when_no_provider_available() -> None:
    client = _client()
    client.ollama = None
    client.openai = None
    client.anthropic = None

    with pytest.raises(mod.LLMError, match="Nenhum provider disponível"):
        client._repair_ollama("prompt", "system", 4000)
