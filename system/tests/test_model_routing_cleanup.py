from __future__ import annotations

from types import SimpleNamespace

import llm_client
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


def test_repair_yaml_deduplicates_same_cloud_and_fallback_model() -> None:
    client = llm_client.LLMClient()
    client.llm_config = SimpleNamespace(
        OLLAMA_MODEL_CLOUD="same-model",
        OLLAMA_MODEL_CLOUD_FALLBACK="same-model",
        OPENAI_MODEL="gpt-test",
        ANTHROPIC_MODEL="claude-test",
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
