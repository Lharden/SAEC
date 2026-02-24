from __future__ import annotations

from types import SimpleNamespace

import llm_client
import llm_client_quotes
import pipeline_cascade
from config import LLMConfig


class _FakeCompletions:
    def __init__(self, outcomes: dict[str, str | Exception]) -> None:
        self._outcomes = outcomes
        self.calls: list[str] = []

    def create(self, *, model: str, **kwargs):
        self.calls.append(model)
        outcome = self._outcomes.get(model, "---\nok: true\n---")
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=outcome))]
        )


def _openai_like_client(outcomes: dict[str, str | Exception]):
    completions = _FakeCompletions(outcomes)
    return SimpleNamespace(
        chat=SimpleNamespace(completions=completions), _calls=completions
    )


def test_llm_config_does_not_require_anthropic_when_ollama_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv("USE_TWO_PASS", "true")

    cfg = LLMConfig()
    errors = cfg.validate()

    assert not any("ANTHROPIC_API_KEY" in error for error in errors)


def test_llm_config_treats_template_keys_as_placeholders(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your-anthropic-api-key-here")
    monkeypatch.setenv("OPENAI_API_KEY", "your-openai-api-key-here")
    monkeypatch.setenv("OLLAMA_ENABLED", "false")

    cfg = LLMConfig()
    errors = cfg.validate()
    masked = cfg.get_masked_keys()

    assert any("Nenhum provider disponível" in error for error in errors)
    assert "placeholder" in masked["anthropic"].lower()
    assert "placeholder" in masked["openai"].lower()


def test_llm_config_rejects_invalid_function_provider_route(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    monkeypatch.setenv("PROVIDER_EXTRACT", "invalid-provider")

    cfg = LLMConfig()
    errors = cfg.validate()

    assert any("PROVIDER_EXTRACT inválido" in error for error in errors)


def test_llm_config_does_not_require_primary_provider_when_all_routes_are_explicit(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv("PRIMARY_PROVIDER", "openai")
    monkeypatch.setenv("PROVIDER_EXTRACT", "ollama")
    monkeypatch.setenv("PROVIDER_REPAIR", "ollama")
    monkeypatch.setenv("PROVIDER_QUOTES", "ollama")
    monkeypatch.setenv("PROVIDER_CASCADE_API", "anthropic")

    cfg = LLMConfig()
    errors = cfg.validate()

    assert not any("PRIMARY_PROVIDER=" in error for error in errors)


def _retry_defaults() -> dict:
    return dict(
        RETRY_MAX_RETRIES=0,
        RETRY_BASE_DELAY=0.0,
        RETRY_MAX_DELAY=0.0,
        RETRY_JITTER=0.0,
        RETRY_MAX_ELAPSED=10.0,
    )


def test_repair_yaml_deduplicates_same_cloud_and_fallback_model() -> None:
    client = llm_client.LLMClient()
    client.llm_config = SimpleNamespace(
        OLLAMA_MODEL_CLOUD="same-model",
        OLLAMA_MODEL_CLOUD_FALLBACK="same-model",
        OPENAI_MODEL="gpt-test",
        ANTHROPIC_MODEL="claude-test",
        **_retry_defaults(),
    )

    ollama = _openai_like_client({"same-model": RuntimeError("cloud down")})
    openai = _openai_like_client({"gpt-test": "---\nfixed: true\n---"})

    client.ollama = ollama
    client.openai = openai
    client.anthropic = None

    result = client.repair_yaml(
        yaml_content="---\na: 1\n---",
        errors=["erro de teste"],
        provider="ollama",
    )

    assert "fixed: true" in result
    assert ollama._calls.calls == ["same-model"]
    assert openai._calls.calls == ["gpt-test"]


def test_ollama_hybrid_routes_text_to_cloud_and_image_to_vision() -> None:
    client = llm_client.LLMClient()
    client.llm_config = SimpleNamespace(
        OLLAMA_MODEL_CLOUD="cloud-model",
        OLLAMA_MODEL_VISION="vision-model",
    )

    ollama = _openai_like_client(
        {
            "cloud-model": "---\nsource: cloud\n---",
            "vision-model": "---\nsource: vision\n---",
        }
    )
    client.ollama = ollama
    client._call_with_retry = lambda fn, **kwargs: fn()  # type: ignore[method-assign]

    text_content = [{"type": "text", "text": "conteudo textual"}]
    image_content = [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}
    ]

    client._call_ollama_hybrid(text_content, "intro", 1000, artigo_id="ART_TEST")
    client._call_ollama_hybrid(image_content, "intro", 1000, artigo_id="ART_TEST")

    assert ollama._calls.calls == ["cloud-model", "vision-model"]


def test_extract_cascade_api_only_reports_openai_source(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_cascade.llm_config, "PRIMARY_PROVIDER", "openai")

    def _fake_extract_with_api(*args, **kwargs):
        return "---\nArtigoID: ART_TEST\n---", pipeline_cascade.CascadeMetrics(
            api_time_ms=1.0,
            total_time_ms=1.0,
        )

    monkeypatch.setattr(pipeline_cascade, "extract_with_api", _fake_extract_with_api)
    monkeypatch.setattr(
        pipeline_cascade,
        "_validate_yaml",
        lambda yaml_content, artigo_id: SimpleNamespace(
            is_valid=True,
            errors=[],
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        pipeline_cascade,
        "_estimate_confidence",
        lambda yaml_content, validation: 0.9,
    )

    result = pipeline_cascade.extract_cascade(
        artigo_id="ART_TEST",
        text="demo",
        prompt_template="{TEXT}",
        strategy="api_only",
    )

    assert result.source == pipeline_cascade.ExtractionSource.API_OPENAI


def test_extract_cascade_prefers_configured_cascade_api_provider(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_cascade.llm_config, "PRIMARY_PROVIDER", "anthropic")
    monkeypatch.setattr(pipeline_cascade.llm_config, "PROVIDER_CASCADE_API", "openai")
    monkeypatch.setattr(pipeline_cascade.llm_config, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(pipeline_cascade.llm_config, "ANTHROPIC_API_KEY", "")

    called: dict[str, str] = {}

    def _fake_extract_with_api(*args, **kwargs):
        called["provider"] = kwargs.get("provider", "")
        return "---\nArtigoID: ART_TEST\n---", pipeline_cascade.CascadeMetrics(
            api_time_ms=1.0,
            total_time_ms=1.0,
        )

    monkeypatch.setattr(pipeline_cascade, "extract_with_api", _fake_extract_with_api)
    monkeypatch.setattr(
        pipeline_cascade,
        "_validate_yaml",
        lambda yaml_content, artigo_id: SimpleNamespace(
            is_valid=True,
            errors=[],
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        pipeline_cascade,
        "_estimate_confidence",
        lambda yaml_content, validation: 0.9,
    )

    result = pipeline_cascade.extract_cascade(
        artigo_id="ART_TEST",
        text="demo",
        prompt_template="{TEXT}",
        strategy="api_only",
    )

    assert called["provider"] == "openai"
    assert result.source == pipeline_cascade.ExtractionSource.API_OPENAI


def test_llm_client_passes_openai_base_url_to_openai_init(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(llm_client, "OpenAI", _FakeOpenAI)

    cfg = SimpleNamespace(
        ANTHROPIC_API_KEY="",
        OPENAI_API_KEY="api-key",
        OPENAI_BASE_URL="https://openrouter.ai/api/v1",
        OLLAMA_ENABLED=False,
        get_httpx_timeout=lambda: 30.0,
    )
    ctx = SimpleNamespace(llm_config=cfg, paths=SimpleNamespace())

    _client = llm_client.LLMClient(context=ctx)

    assert calls
    assert calls[0]["api_key"] == "api-key"
    assert calls[0]["base_url"] == "https://openrouter.ai/api/v1"


def test_openai_hybrid_retries_without_prompt_cache_kwargs_on_legacy_sdk() -> None:
    class _LegacyCompletions:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def create(self, *, model: str, max_completion_tokens: int, messages):
            self.calls.append(
                {
                    "model": model,
                    "max_completion_tokens": max_completion_tokens,
                    "messages": messages,
                }
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="---\nok: true\n---"))],
                usage=None,
            )

    client = llm_client.LLMClient()
    client.llm_config = SimpleNamespace(
        OPENAI_MODEL="gpt-test",
        PROMPT_CACHE_ENABLED=True,
        PROMPT_CACHE_KEY="saec-test",
        PROMPT_CACHE_RETENTION="in_memory",
    )
    legacy = _LegacyCompletions()
    client.openai = SimpleNamespace(chat=SimpleNamespace(completions=legacy))
    client._call_with_retry = lambda fn, **kwargs: fn()  # type: ignore[method-assign]

    result = client._call_openai_hybrid(
        content=[{"type": "text", "text": "conteudo"}],
        intro="intro",
        max_tokens=512,
        artigo_id="ART_TEST",
        system_prompt="system",
    )

    assert "ok: true" in result
    # A primeira tentativa com kwargs de cache falha no SDK legado e a segunda sem cache passa.
    assert len(legacy.calls) == 1


def test_openai_image_block_is_converted_for_anthropic_quotes() -> None:
    converted = llm_client_quotes._openai_image_to_anthropic_block(
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,abcd1234"},
        }
    )

    assert converted is not None
    assert converted["type"] == "image"
    assert converted["source"]["type"] == "base64"
    assert converted["source"]["media_type"] == "image/png"
    assert converted["source"]["data"] == "abcd1234"
