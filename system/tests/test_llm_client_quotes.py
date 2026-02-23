from __future__ import annotations

import importlib
from types import SimpleNamespace

import llm_client_quotes as mod


class _Client(mod.LLMClientQuotesMixin):
    def __init__(self) -> None:
        self.anthropic = None
        self.openai = None
        self.ollama = None

    def _check_provider(self, provider: object) -> None:
        return None

    def postprocess_extraction(self, yaml_content: str, use_llm_format: bool = True) -> str:
        return yaml_content


def _valid_result() -> SimpleNamespace:
    return SimpleNamespace(is_valid=True, errors=[], warnings=[])


def _invalid_result() -> SimpleNamespace:
    return SimpleNamespace(is_valid=False, errors=["x"], warnings=[])


def test_openai_image_to_anthropic_block_converts_data_url() -> None:
    block = {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,AAAA"},
    }
    out = mod._openai_image_to_anthropic_block(block)
    assert out is not None
    assert out["type"] == "image"
    assert out["source"]["media_type"] == "image/png"
    assert out["source"]["data"] == "AAAA"


def test_openai_image_to_anthropic_block_rejects_invalid_block() -> None:
    assert mod._openai_image_to_anthropic_block({"type": "text"}) is None
    assert mod._openai_image_to_anthropic_block({"type": "image_url", "image_url": {"url": "http://x"}}) is None


def test_reextract_quotes_openai_path_returns_message_content() -> None:
    expected = "Quotes:\n  - QuoteID: Q001"
    client = _Client()
    client.openai = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=expected))]
                )
            )
        )
    )

    out = client.reextract_quotes(
        images=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}],
        current_yaml="ArtigoID: ART_001",
        provider="openai",
    )
    assert out == expected


def test_reextract_quotes_anthropic_path_converts_images() -> None:
    client = _Client()
    client.anthropic = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                content=[SimpleNamespace(text=f"count={len(kwargs['messages'][0]['content'])}")]
            )
        )
    )

    out = client.reextract_quotes(
        images=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}],
        current_yaml="ArtigoID: ART_001",
        provider="anthropic",
    )
    assert out == "count=2"  # imagem convertida + prompt textual


def test_extract_validated_with_fallback_reextracts_when_quotes_missing(monkeypatch) -> None:
    client = _Client()
    calls: list[str] = []
    current = {"n": 0}

    def _fake_validate(_yaml: str) -> SimpleNamespace:
        current["n"] += 1
        return _invalid_result() if current["n"] == 1 else _valid_result()

    def _fake_import(name: str, package: str | None = None):
        if name in {".validators", "validators"}:
            return SimpleNamespace(validate_yaml=_fake_validate)
        return real_import(name, package=package)

    def _fake_reextract(**_: object) -> str:
        calls.append("reextract")
        return (
            "Quotes:\n"
            "  - QuoteID: Q001\n"
            "    TipoQuote: Contexto\n"
            "    Trecho: trecho literal relevante\n"
            "    Página: p.1\n"
        )

    real_import = importlib.import_module
    monkeypatch.setattr(importlib, "import_module", _fake_import)
    monkeypatch.setattr(mod, "extract_yaml_from_response", lambda text: text)
    monkeypatch.setattr(client, "reextract_quotes", _fake_reextract)

    yaml_in = "ArtigoID: ART_001\nQuotes: []\n"
    content_openai = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]

    out_yaml, result = client.extract_validated_with_fallback(
        yaml_only=yaml_in,
        content_openai=content_openai,
        max_attempts=1,
    )

    assert calls == ["reextract"]
    assert "QuoteID: Q001" in out_yaml
    assert result.is_valid is True

