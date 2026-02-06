"""Mixin de pós-processamento para YAML extraído."""

from __future__ import annotations

import logging
import importlib
from typing import Any


def _load_llm_config():
    try:
        return importlib.import_module(".config", package=__package__).llm_config
    except Exception:  # pragma: no cover - standalone usage
        return importlib.import_module("config").llm_config


llm_config = _load_llm_config()

logger = logging.getLogger(__name__)


class LLMClientPostprocessMixin:
    """Mixin com rotinas de pós-processamento."""
    ollama: Any

    def format_yaml(
        self,
        raw_yaml: str,
        max_tokens: int = 4000,
    ) -> str:
        """Formata/normaliza YAML antes da validação usando modelo local."""
        if not self.ollama:
            logger.debug("Ollama indisponivel, retornando YAML sem formatacao")
            return raw_yaml

        format_prompt = f"""Formate o YAML abaixo para ser valido e bem estruturado.

REGRAS:
1. Corrija indentacao (2 espacos por nivel)
2. Remova caracteres invalidos ou de controle
3. Normalize strings multiline para formato YAML correto
4. NAO altere o conteudo, apenas o formato
5. Retorne SOMENTE o YAML formatado, sem explicacoes

YAML:
```yaml
{raw_yaml}
```

YAML formatado:"""

        try:
            model = llm_config.OLLAMA_MODEL_CODER
            response = self.ollama.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": "Voce e um formatador de YAML. Retorne APENAS YAML valido.",
                    },
                    {"role": "user", "content": format_prompt},
                ],
            )
            result = response.choices[0].message.content
            logger.debug("YAML formatado via Ollama")
            return result
        except Exception as e:
            logger.warning("Falha ao formatar YAML via Ollama: %s", e)
            return raw_yaml

    def normalize_yaml(self, yaml_content: str) -> str:
        """Normalização mecânica de YAML (sem LLM)."""
        import re

        if not yaml_content:
            return yaml_content

        text = yaml_content
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"^(\s*)(\w+)\s+:", r"\1\2:", text, flags=re.MULTILINE)

        replacements = {
            "â€“": "–",
            "â€”": "—",
            "â€™": "'",
            "â€œ": '"',
            "â€": '"',
            "Ã©": "é",
            "Ã£": "ã",
            "Ã§": "ç",
            "Ã³": "ó",
            "Ãº": "ú",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        if text and not text.endswith("\n"):
            text += "\n"

        return text

    def postprocess_extraction(
        self,
        yaml_content: str,
        use_llm_format: bool = True,
    ) -> str:
        """Pipeline completo de pós-processamento."""
        result = self.normalize_yaml(yaml_content)

        try:
            postprocess_mod = importlib.import_module(".postprocess", package=__package__)
        except Exception:
            try:
                postprocess_mod = importlib.import_module("postprocess")
            except Exception:
                postprocess_mod = None

        if postprocess_mod is not None:
            result = postprocess_mod.postprocess_yaml(result)
        else:
            logger.warning("postprocess module not found, skipping deterministic corrections")

        if use_llm_format and self.ollama:
            result = self.format_yaml(result)

        return result
