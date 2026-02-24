from __future__ import annotations

from adapters import ollama_adapter


def _response_with_none_metrics(content: str) -> dict[str, object]:
    return {
        "message": {"content": content},
        "prompt_eval_count": None,
        "eval_count": None,
        "total_duration": None,
        "load_duration": None,
    }


def test_generate_text_handles_none_metrics(monkeypatch) -> None:
    def _fake_chat(**_kwargs):
        return _response_with_none_metrics("ok")

    monkeypatch.setattr(ollama_adapter.ollama, "chat", _fake_chat)

    response = ollama_adapter.generate_text("hello", model="qwen3-vl:8b")

    assert response.content == "ok"
    assert response.prompt_tokens == 0
    assert response.completion_tokens == 0
    assert response.total_tokens == 0
    assert response.total_duration_ms == 0.0
    assert response.load_duration_ms == 0.0


def test_generate_vision_handles_none_metrics(monkeypatch) -> None:
    def _fake_chat(**_kwargs):
        return _response_with_none_metrics("vision-ok")

    monkeypatch.setattr(ollama_adapter.ollama, "chat", _fake_chat)

    response = ollama_adapter.generate_vision(
        prompt="describe",
        images=["base64-image"],
        model="qwen3-vl:8b",
    )

    assert response.content == "vision-ok"
    assert response.prompt_tokens == 0
    assert response.completion_tokens == 0
    assert response.total_tokens == 0
    assert response.total_duration_ms == 0.0
    assert response.load_duration_ms == 0.0
