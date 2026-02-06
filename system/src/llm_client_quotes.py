"""Mixins para rotinas de reextração e validação com fallback."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Tuple, TYPE_CHECKING

try:
    from rapidfuzz import fuzz as _fuzz  # type: ignore
except Exception:  # pragma: no cover
    _fuzz = None


def _load_llm_config():
    try:
        return importlib.import_module(".config", package=__package__).llm_config
    except Exception:  # pragma: no cover - standalone usage
        return importlib.import_module("config").llm_config


def _load_extract_yaml_from_response():
    try:
        return importlib.import_module(".llm_utils", package=__package__).extract_yaml_from_response
    except Exception:  # pragma: no cover - standalone usage
        return importlib.import_module("llm_utils").extract_yaml_from_response


llm_config = _load_llm_config()
extract_yaml_from_response = _load_extract_yaml_from_response()

def _load_extraction_config():
    try:
        return importlib.import_module(".config", package=__package__).extraction_config
    except Exception:  # pragma: no cover
        return importlib.import_module("config").extraction_config

extraction_config = _load_extraction_config()

if TYPE_CHECKING:
    from .llm_client_types import Provider as ProviderType
    from .validators import ValidationResult
else:
    ProviderType = Any
    ValidationResult = Any

logger = logging.getLogger(__name__)


class LLMClientQuotesMixin:
    """Mixin com rotinas de quotes e validação."""
    anthropic: Any
    openai: Any
    ollama: Any

    def _check_provider(self, provider: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def postprocess_extraction(self, yaml_content: str, use_llm_format: bool = True) -> str:  # pragma: no cover
        raise NotImplementedError

    def extract_validated_with_fallback(
        self,
        *,
        # Forneça os conteúdos já preparados no formato do provider.
        # - Para provider=openai/ollama: use content_openai (blocks com text + image_url)
        # - Para provider=anthropic: use content_anthropic (blocks com text + image)
        yaml_only: str,
        content_openai: list[dict] | None = None,
        provider: ProviderType = "anthropic",
        fallback_provider: ProviderType = "openai",
        max_attempts: int = 2,
        max_tokens: int = 4000,
    ) -> Tuple[str, "ValidationResult"]:
        """
        Valida YAML e tenta reparar quotes quando necessário.

        Heurística objetiva (sem olhar imagens):
        - Para quotes cujo 'Página' corresponde a uma página enviada como TEXTO no conteúdo híbrido,
          verificamos se o trecho aparece literalmente no texto extraído (normalizando espaços).
        - Se alguma dessas quotes não bater, reextrai a seção de Quotes.
        """
        import importlib

        try:
            validators_mod = importlib.import_module(".validators", package=__package__)
        except Exception:  # pragma: no cover - standalone usage
            validators_mod = importlib.import_module("validators")

        validate_yaml = validators_mod.validate_yaml

        import yaml as _yaml
        import re as _re

        # 1) Parse YAML para acessar Quotes
        try:
            docs = list(_yaml.safe_load_all(yaml_only))
            data = docs[0] if docs else None
        except Exception:
            return yaml_only, validate_yaml(yaml_only)

        if not isinstance(data, dict):
            return yaml_only, validate_yaml(yaml_only)

        quotes = data.get("Quotes", [])

        # Se quotes estão ausentes ou insuficientes, tentar reextração.
        if not isinstance(quotes, list) or len(quotes) < 3:
            images = []
            if content_openai:
                images = [b for b in content_openai if isinstance(b, dict) and b.get("type") == "image_url"]
            if images and max_attempts > 0:
                current = yaml_only
                last_result = validate_yaml(current)
                for _ in range(max_attempts):
                    try:
                        quotes_section = self.reextract_quotes(
                            images=images,
                            current_yaml=current,
                            provider=provider,
                            max_tokens=max_tokens,
                        )
                    except Exception:
                        if provider != fallback_provider:
                            quotes_section = self.reextract_quotes(
                                images=images,
                                current_yaml=current,
                                provider=fallback_provider,
                                max_tokens=max_tokens,
                            )
                        else:
                            break

                    if "Quotes:" in quotes_section:
                        prefix = current.split("Quotes:", 1)[0].rstrip() + "\n"
                        qs = quotes_section
                        if "```" in qs:
                            qs = qs.split("```", 2)[1] if qs.count("```") >= 2 else qs
                        current = prefix + qs.strip() + "\n"

                    current = extract_yaml_from_response(current)
                    current = self.postprocess_extraction(current, use_llm_format=False)
                    last_result = validate_yaml(current)
                    if last_result.is_valid:
                        return current, last_result

                return current, last_result

            return yaml_only, validate_yaml(yaml_only)

        # 2) Construir mapa page_num -> texto (somente páginas que foram enviadas como texto)
        page_text: dict[int, str] = {}
        if content_openai:
            for block in content_openai:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "text":
                    continue
                t = block.get("text") or ""
                m = _re.match(r"^---\s*P[áa]gina\s+(\d+)\s*\(texto\)\s*---\n(.*)$", t, flags=_re.DOTALL)
                if m:
                    page = int(m.group(1))
                    txt = m.group(2)
                    page_text[page] = txt

        def _norm(s: str) -> str:
            return " ".join((s or "").split()).strip().lower()

        def _is_quote_match(trecho: str, page_text_value: str) -> bool:
            t_norm = _norm(trecho)
            p_norm = _norm(page_text_value)
            if not t_norm or not p_norm:
                return False
            if t_norm in p_norm:
                return True
            if _fuzz is not None:
                ratio = _fuzz.partial_ratio(t_norm, p_norm) / 100.0
                return ratio >= float(extraction_config.QUOTE_MATCH_RATIO)
            return False

        mismatches = 0
        for q in quotes:
            if not isinstance(q, dict):
                continue
            trecho = q.get("Trecho", "")
            pagina = q.get("Página") or q.get("Pagina") or q.get("page")
            if not isinstance(trecho, str) or not trecho.strip():
                continue
            if not isinstance(pagina, str):
                continue

            m = _re.search(r"p\.(\d+)", pagina)
            if not m:
                continue
            pnum = int(m.group(1))

            # Só checar literalidade quando temos texto da página
            if pnum in page_text:
                if not _is_quote_match(trecho, page_text[pnum]):
                    mismatches += 1

        if mismatches == 0:
            return yaml_only, validate_yaml(yaml_only)

        # 3) Reextrair quotes (somente imagens do conteúdo híbrido)
        images = []
        if content_openai:
            images = [b for b in content_openai if isinstance(b, dict) and b.get("type") == "image_url"]

        if not images:
            return yaml_only, validate_yaml(yaml_only)

        current = yaml_only
        last_result = validate_yaml(current)

        for _ in range(max_attempts):
            try:
                quotes_section = self.reextract_quotes(
                    images=images,
                    current_yaml=current,
                    provider=provider,
                    max_tokens=max_tokens,
                )
            except Exception:
                if provider != fallback_provider:
                    quotes_section = self.reextract_quotes(
                        images=images,
                        current_yaml=current,
                        provider=fallback_provider,
                        max_tokens=max_tokens,
                    )
                else:
                    break

            if "Quotes:" in quotes_section:
                prefix = current.split("Quotes:", 1)[0].rstrip() + "\n"
                qs = quotes_section
                if "```" in qs:
                    qs = qs.split("```", 2)[1] if qs.count("```") >= 2 else qs
                current = prefix + qs.strip() + "\n"

            current = extract_yaml_from_response(current)
            current = self.postprocess_extraction(current, use_llm_format=False)
            last_result = validate_yaml(current)

        return current, last_result

    def reextract_quotes(
        self,
        images: list[dict],
        current_yaml: str,
        provider: ProviderType = "anthropic",
        max_tokens: int = 4000,
    ) -> str:
        """Reextrai apenas as quotes de um artigo."""
        self._check_provider(provider)

        prompt = f"""O YAML abaixo precisa de mais quotes ou quotes melhores.

YAML ATUAL:
```yaml
{current_yaml}
```

TAREFA:
Analise novamente o artigo e extraia 5-6 quotes que:
1. Sejam LITERAIS (cópia exata do texto)
2. Tenham no máximo 3 linhas cada
3. Incluam a página de origem (p.X)
4. Priorizem quotes de MECANISMO (como/por que a IA gera valor)

Retorne APENAS a seção de Quotes no formato:
```yaml
Quotes:
  - QuoteID: Q001
    TipoQuote: "..."
    Trecho: "..."
    Página: "p.X"
```"""

        content = list(images) + [{"type": "text", "text": prompt}]

        if provider == "ollama":
            model = llm_config.OLLAMA_MODEL_CODER
            response = self.ollama.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            return response.choices[0].message.content

        if provider == "anthropic":
            response = self.anthropic.messages.create(
                model=llm_config.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            return response.content[0].text

        response = self.openai.chat.completions.create(
            model=llm_config.OPENAI_MODEL,
            max_completion_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content
