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
