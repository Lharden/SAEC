from __future__ import annotations

from types import SimpleNamespace

import llm_client_postprocess as mod


class _Client(mod.LLMClientPostprocessMixin):
    def __init__(self, ollama: object | None = None) -> None:
        self.ollama = ollama


def _fake_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


def test_format_yaml_returns_input_when_ollama_missing() -> None:
    client = _Client(ollama=None)
    raw = "a: 1"
    assert client.format_yaml(raw) == raw


def test_format_yaml_uses_ollama_when_available() -> None:
    ollama = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: _fake_response("x: 1\n"),
            )
        )
    )
    client = _Client(ollama=ollama)

    assert client.format_yaml("broken") == "x: 1\n"


def test_format_yaml_falls_back_on_ollama_error() -> None:
    def _boom(**_: object) -> SimpleNamespace:
        raise OSError("network")

    ollama = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=_boom),
        )
    )
    client = _Client(ollama=ollama)

    assert client.format_yaml("raw: value") == "raw: value"


def test_normalize_yaml_applies_line_and_encoding_fixes() -> None:
    client = _Client()
    normalized = client.normalize_yaml("k : v\r\nline Ã©\r\n")
    assert "k: v" in normalized
    assert "line é" in normalized
    assert normalized.endswith("\n")


def test_postprocess_extraction_applies_domain_postprocess(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(_Client, "_should_apply_domain_postprocess", staticmethod(lambda: True))
    monkeypatch.setattr(
        mod,
        "_postprocess_module",
        SimpleNamespace(postprocess_yaml=lambda text: text + "#post"),
    )

    out = client.postprocess_extraction("a: 1", use_llm_format=False)

    assert out.endswith("#post")


def test_should_apply_domain_postprocess_defaults_true_when_import_fails(monkeypatch) -> None:
    import importlib

    real_import = importlib.import_module

    def _fake_import(name: str, package: str | None = None):
        if "profile_engine.project_profiles" in name:
            raise ImportError("missing")
        return real_import(name, package=package)

    monkeypatch.setattr(importlib, "import_module", _fake_import)

    assert mod.LLMClientPostprocessMixin._should_apply_domain_postprocess() is True

