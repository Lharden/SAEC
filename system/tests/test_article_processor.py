from __future__ import annotations

import json
from pathlib import Path

from processors import ArticleProcessor
from validators import validate_yaml


class DummyClient:
    def __init__(self, yaml_text: str) -> None:
        self._yaml = yaml_text
        self.llm_config = type("Cfg", (), {"MAX_REPAIR_ATTEMPTS": 1, "PRIMARY_PROVIDER": "anthropic"})()
        self.anthropic = object()
        self.openai = object()
        self.ollama = None

    def extract_with_hybrid(self, *, content, prompt, artigo_id, provider, max_tokens):
        return self._yaml

    def postprocess_extraction(self, yaml_content: str, use_llm_format: bool = True) -> str:
        return yaml_content

    def repair_yaml(self, yaml_content: str, errors: list[str], provider: str, max_tokens: int = 8000) -> str:
        return yaml_content

    def extract_validated_with_fallback(
        self,
        *,
        yaml_only: str,
        content_openai,
        provider,
        fallback_provider,
        max_attempts,
        max_tokens,
    ):
        return yaml_only, validate_yaml(yaml_only)


def test_article_processor_process_article(tmp_path: Path, monkeypatch):
    # Desabilitar cascade para teste isolado
    import config
    monkeypatch.setattr(config.local_config, "USE_CASCADE", False)

    yaml_text = (Path(__file__).parent / "fixtures" / "valid_extraction.yaml").read_text(encoding="utf-8")
    client = DummyClient(yaml_text)

    guia_path = tmp_path / "guia.md"
    guia_path.write_text("prompt", encoding="utf-8")

    work_dir = tmp_path / "work" / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "texts.json").write_text(json.dumps({"1": "dummy text"}), encoding="utf-8")

    hybrid_meta = {
        "pages_info": [{"page_num": 1, "type": "text"}],
        "analysis": [],
        "stats": {},
    }

    processor = ArticleProcessor(
        client=client,
        guia_path=guia_path,
        output_dir=tmp_path / "yamls",
        work_dir=tmp_path / "work",
    )

    yaml_out, result = processor.process_article(
        artigo_id="ART_001",
        hybrid_meta=hybrid_meta,
        work_dir=work_dir,
    )

    assert result.is_valid
    assert "ArtigoID" in yaml_out


def test_article_processor_routes_repair_to_ollama_after_local_cascade(
    tmp_path: Path, monkeypatch
):
    import config
    import pipeline_cascade

    monkeypatch.setattr(config.local_config, "USE_CASCADE", True)
    monkeypatch.setattr(config.local_config, "EXTRACTION_STRATEGY", "local_first")

    valid_yaml = (
        Path(__file__).parent / "fixtures" / "valid_extraction.yaml"
    ).read_text(encoding="utf-8")
    invalid_yaml = "ArtigoID: ART_001"

    class _CascadeClient(DummyClient):
        def __init__(self, yaml_text: str) -> None:
            super().__init__(yaml_text)
            self.ollama = object()
            self.openai = None
            self.last_repair_provider = None

        def repair_yaml(
            self,
            yaml_content: str,
            errors: list[str],
            provider: str,
            max_tokens: int = 8000,
        ) -> str:
            self.last_repair_provider = provider
            return valid_yaml

    client = _CascadeClient(valid_yaml)

    def _fake_extract_cascade(*args, **kwargs):
        return pipeline_cascade.CascadeResult(
            yaml_content=invalid_yaml,
            source=pipeline_cascade.ExtractionSource.LOCAL_OLLAMA,
            confidence=0.2,
            validation=None,
            metrics=pipeline_cascade.CascadeMetrics(),
            success=False,
            error="API escalation failed",
        )

    monkeypatch.setattr(pipeline_cascade, "extract_cascade", _fake_extract_cascade)

    guia_path = tmp_path / "guia.md"
    guia_path.write_text("prompt", encoding="utf-8")

    work_dir = tmp_path / "work" / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "texts.json").write_text(json.dumps({"1": "dummy text"}), encoding="utf-8")

    hybrid_meta = {
        "pages_info": [{"page_num": 1, "type": "text"}],
        "analysis": [],
        "stats": {},
    }

    processor = ArticleProcessor(
        client=client,
        guia_path=guia_path,
        output_dir=tmp_path / "yamls",
        work_dir=tmp_path / "work",
    )

    _, result = processor.process_article(
        artigo_id="ART_001",
        hybrid_meta=hybrid_meta,
        work_dir=work_dir,
    )

    assert result.is_valid
    assert client.last_repair_provider == "ollama"


def test_article_processor_applies_function_provider_routing(
    tmp_path: Path, monkeypatch
) -> None:
    import config

    monkeypatch.setattr(config.local_config, "USE_CASCADE", False)

    valid_yaml = (
        Path(__file__).parent / "fixtures" / "valid_extraction.yaml"
    ).read_text(encoding="utf-8")
    invalid_yaml = "ArtigoID: ART_001"

    class _RoutingClient(DummyClient):
        def __init__(self) -> None:
            super().__init__(invalid_yaml)
            self.llm_config = type(
                "Cfg",
                (),
                {
                    "MAX_REPAIR_ATTEMPTS": 1,
                    "PRIMARY_PROVIDER": "ollama",
                    "PROVIDER_EXTRACT": "openai",
                    "PROVIDER_REPAIR": "anthropic",
                    "PROVIDER_QUOTES": "auto",
                },
            )()
            self.anthropic = object()
            self.openai = object()
            self.ollama = object()
            self.extract_provider = None
            self.repair_provider = None

        def extract_with_hybrid(
            self, *, content, prompt, artigo_id, provider, max_tokens
        ):
            self.extract_provider = provider
            return invalid_yaml

        def repair_yaml(
            self,
            yaml_content: str,
            errors: list[str],
            provider: str,
            max_tokens: int = 8000,
        ) -> str:
            self.repair_provider = provider
            return valid_yaml

    client = _RoutingClient()

    guia_path = tmp_path / "guia.md"
    guia_path.write_text("prompt", encoding="utf-8")

    work_dir = tmp_path / "work" / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "texts.json").write_text(json.dumps({"1": "dummy text"}), encoding="utf-8")

    hybrid_meta = {
        "pages_info": [{"page_num": 1, "type": "text"}],
        "analysis": [],
        "stats": {},
    }

    processor = ArticleProcessor(
        client=client,
        guia_path=guia_path,
        output_dir=tmp_path / "yamls",
        work_dir=tmp_path / "work",
    )

    yaml_out, result = processor.process_article(
        artigo_id="ART_001",
        hybrid_meta=hybrid_meta,
        work_dir=work_dir,
    )

    assert result.is_valid
    assert "ArtigoID" in yaml_out
    assert client.extract_provider == "openai"
    assert client.repair_provider == "anthropic"


def test_article_processor_falls_back_when_routed_provider_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    import config

    monkeypatch.setattr(config.local_config, "USE_CASCADE", False)

    valid_yaml = (
        Path(__file__).parent / "fixtures" / "valid_extraction.yaml"
    ).read_text(encoding="utf-8")

    class _FallbackClient(DummyClient):
        def __init__(self) -> None:
            super().__init__(valid_yaml)
            self.llm_config = type(
                "Cfg",
                (),
                {
                    "MAX_REPAIR_ATTEMPTS": 1,
                    "PRIMARY_PROVIDER": "openai",
                    "PROVIDER_EXTRACT": "openai",
                    "PROVIDER_REPAIR": "auto",
                    "PROVIDER_QUOTES": "auto",
                },
            )()
            self.anthropic = None
            self.openai = None
            self.ollama = object()
            self.extract_provider = None

        def extract_with_hybrid(
            self, *, content, prompt, artigo_id, provider, max_tokens
        ):
            self.extract_provider = provider
            return valid_yaml

    client = _FallbackClient()

    guia_path = tmp_path / "guia.md"
    guia_path.write_text("prompt", encoding="utf-8")

    work_dir = tmp_path / "work" / "ART_001"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "texts.json").write_text(json.dumps({"1": "dummy text"}), encoding="utf-8")

    hybrid_meta = {
        "pages_info": [{"page_num": 1, "type": "text"}],
        "analysis": [],
        "stats": {},
    }

    processor = ArticleProcessor(
        client=client,
        guia_path=guia_path,
        output_dir=tmp_path / "yamls",
        work_dir=tmp_path / "work",
    )

    _, result = processor.process_article(
        artigo_id="ART_001",
        hybrid_meta=hybrid_meta,
        work_dir=work_dir,
    )

    assert result.is_valid
    assert client.extract_provider == "ollama"
