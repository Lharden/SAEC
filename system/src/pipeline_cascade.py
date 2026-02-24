"""Pipeline de extração em cascata com estratégia cloud/local + fallback de API."""

from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if __package__:
    from . import config as _config
    from . import exceptions as _exceptions
    from . import validators as _validators
else:  # pragma: no cover - standalone usage
    _config = importlib.import_module("config")
    _exceptions = importlib.import_module("exceptions")
    _validators = importlib.import_module("validators")

if TYPE_CHECKING:
    if __package__:
        from .validators import ValidationResult
    else:  # pragma: no cover - standalone usage
        from validators import ValidationResult

llm_config = _config.llm_config
local_config = _config.local_config
_is_placeholder_api_key = _config._is_placeholder_api_key
ExtractError = _exceptions.ExtractError
validate_yaml = _validators.validate_yaml

logger = logging.getLogger(__name__)


def _resolve_api_provider(preferred_provider: str) -> str:
    if not hasattr(llm_config, "get_provider_registry"):
        has_openai = not _is_placeholder_api_key(getattr(llm_config, "OPENAI_API_KEY", ""))
        has_anthropic = not _is_placeholder_api_key(getattr(llm_config, "ANTHROPIC_API_KEY", ""))
        preferred = (preferred_provider or "").strip().lower()
        if preferred == "openai" and has_openai:
            return "openai"
        if preferred == "anthropic" and has_anthropic:
            return "anthropic"
        if has_openai:
            return "openai"
        if has_anthropic:
            return "anthropic"
        return "anthropic"

    registry = llm_config.get_provider_registry()
    preferred = (preferred_provider or "").strip().lower()
    if preferred and preferred != "auto":
        if preferred in registry and llm_config.provider_available(preferred):
            if registry[preferred].get("kind", "") != "ollama":
                return preferred

    for provider_id, spec in registry.items():
        if spec.get("kind", "").strip().lower() == "ollama":
            continue
        if llm_config.provider_available(provider_id):
            return provider_id

    # fallback final
    return preferred or "openai"


def _select_cascade_api_provider() -> str:
    configured = str(getattr(llm_config, "PROVIDER_CASCADE_API", "auto")).strip().lower()
    if configured and configured != "auto":
        return configured
    primary = str(getattr(llm_config, "PRIMARY_PROVIDER", "ollama")).strip().lower()
    return primary


def _source_for_api_provider(provider: str) -> ExtractionSource:
    if provider == "openai":
        return ExtractionSource.API_OPENAI
    if provider == "anthropic":
        return ExtractionSource.API_ANTHROPIC
    return ExtractionSource.HYBRID


# ============================================================
# Enums e Data Classes
# ============================================================


class ExtractionSource(Enum):
    """Fonte da extração."""

    LOCAL_OLLAMA = "local_ollama"
    LOCAL_OLLAMA_VISION = "local_ollama_vision"
    API_ANTHROPIC = "api_anthropic"
    API_OPENAI = "api_openai"
    HYBRID = "hybrid"  # Local + API repair


@dataclass
class CascadeMetrics:
    """Métricas de uma extração em cascata."""

    total_time_ms: float = 0.0
    local_time_ms: float = 0.0
    api_time_ms: float = 0.0
    local_tokens: int = 0
    api_tokens: int = 0
    api_cost_estimate: float = 0.0
    attempts: int = 0
    escalated: bool = False
    escalation_reason: str | None = None


@dataclass
class CascadeResult:
    """Resultado de uma extração em cascata."""

    yaml_content: str
    source: ExtractionSource
    confidence: float
    validation: ValidationResult | None
    metrics: CascadeMetrics
    success: bool = True
    error: str | None = None

    @property
    def tokens_saved(self) -> int:
        """Tokens de API economizados por usar local."""
        if self.source in [
            ExtractionSource.LOCAL_OLLAMA,
            ExtractionSource.LOCAL_OLLAMA_VISION,
        ]:
            # Estimativa: extração típica usa ~10K tokens de API
            return 10000
        return 0


@dataclass
class LocalAttemptResult:
    """Resultado agregado das tentativas locais de extração/repair."""

    yaml_content: str = ""
    validation: ValidationResult | None = None
    confidence: float = 0.0
    source: ExtractionSource = ExtractionSource.LOCAL_OLLAMA
    accepted: bool = False


# ============================================================
# Funções de Extração Local
# ============================================================


def extract_with_ollama(
    text: str,
    prompt_template: str,
    *,
    model: str | None = None,
    images: list[Path] | None = None,
    artigo_id: str = "",
) -> tuple[str, CascadeMetrics]:
    """
    Extrai CIMO usando Ollama local.

    Args:
        text: Texto do artigo
        prompt_template: Template do prompt de extração
        model: Modelo Ollama a usar
        images: Imagens opcionais para modelo vision
        artigo_id: ID do artigo para logging

    Returns:
        Tuple (yaml_content, metrics)
    """
    try:
        from .adapters import ollama_adapter
    except ImportError:
        from adapters import ollama_adapter

    metrics = CascadeMetrics()
    start_time = time.time()

    model = model or local_config.OLLAMA_EXTRACTION_MODEL
    mode = "vision" if images else "texto"
    logger.info(
        "Extraction started",
        extra={"artigo_id": artigo_id, "model": model, "action": "extract_local", "mode": mode},
    )

    try:
        # Montar prompt
        full_prompt = prompt_template.replace("{TEXT}", text[:50000])  # Limitar tamanho

        if images:
            response = ollama_adapter.generate_vision(
                full_prompt,
                images,
                model=model,
                temperature=0.1,
                max_tokens=8000,
            )
        else:
            response = ollama_adapter.generate_text(
                full_prompt,
                model=model,
                temperature=0.1,
                max_tokens=8000,
            )

        metrics.local_time_ms = (time.time() - start_time) * 1000
        metrics.local_tokens = response.total_tokens
        metrics.total_time_ms = metrics.local_time_ms
        metrics.attempts = 1

        # Extrair YAML da resposta
        yaml_content = _extract_yaml_block(response.content)

        return yaml_content, metrics

    except ExtractError:
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise
    except Exception as e:
        logger.error(
            "Ollama extraction error: %s",
            e,
            extra={"artigo_id": artigo_id, "model": model, "action": "extract_local"},
        )
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"Ollama extraction failed: {e}") from e


def repair_with_ollama(
    yaml_content: str,
    validation_errors: list[str],
    *,
    model: str | None = None,
    artigo_id: str = "",
) -> tuple[str, CascadeMetrics]:
    """
    Repara YAML inválido usando Ollama local.

    Args:
        yaml_content: YAML com erros
        validation_errors: Lista de erros de validação
        model: Modelo para repair
        artigo_id: ID do artigo

    Returns:
        Tuple (yaml_corrigido, metrics)
    """
    try:
        from .adapters import ollama_adapter
    except ImportError:
        from adapters import ollama_adapter

    metrics = CascadeMetrics()
    start_time = time.time()

    model = model or local_config.OLLAMA_REPAIR_MODEL
    logger.info(
        "Repair started",
        extra={"artigo_id": artigo_id, "model": model, "action": "repair_local"},
    )

    try:
        prompt = f"""Corrija o seguinte YAML baseado nos erros de validação.

ERROS:
{chr(10).join(f"- {e}" for e in validation_errors)}

YAML ORIGINAL:
```yaml
{yaml_content}
```

Retorne APENAS o YAML corrigido, sem explicações.
"""

        response = ollama_adapter.generate_text(
            prompt,
            model=model,
            temperature=0.1,
            max_tokens=8000,
        )

        metrics.local_time_ms = (time.time() - start_time) * 1000
        metrics.local_tokens = response.total_tokens
        metrics.total_time_ms = metrics.local_time_ms
        metrics.attempts = 1

        repaired = _extract_yaml_block(response.content)
        return repaired, metrics

    except ExtractError:
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise
    except Exception as e:
        logger.error(
            "Ollama repair error: %s",
            e,
            extra={"artigo_id": artigo_id, "model": model, "action": "repair_local"},
        )
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"Ollama repair failed: {e}") from e


# ============================================================
# Funções de Extração API
# ============================================================


def _build_api_content_blocks(text: str) -> list[dict[str, str]]:
    """Monta blocos de texto para payload multimodal de extração API."""
    return [{"type": "text", "text": text[:100000]}]


def _extract_yaml_from_response(response: object) -> str:
    if isinstance(response, str):
        return _extract_yaml_block(response)
    if hasattr(response, "content"):
        return _extract_yaml_block(str(getattr(response, "content")))
    return _extract_yaml_block(str(response))


def _estimate_api_cost(provider: str, tokens: int) -> float:
    if provider == "anthropic":
        return tokens * 0.000009
    return tokens * 0.00001


def extract_with_api(
    text: str,
    prompt_template: str,
    *,
    provider: str = "openai",
    images: list[Path] | None = None,
    artigo_id: str = "",
    client: Any | None = None,
) -> tuple[str, CascadeMetrics]:
    """
    Extrai CIMO usando API (Anthropic/OpenAI).

    Args:
        text: Texto do artigo
        prompt_template: Template do prompt
        provider: Provider da API
        images: Imagens opcionais
        artigo_id: ID do artigo
        client: LLMClient existente (evita criar novo a cada chamada)

    Returns:
        Tuple (yaml_content, metrics)
    """
    try:
        from .context import make_context
        from .llm_client import LLMClient
    except ImportError:
        from context import make_context
        from llm_client import LLMClient

    metrics = CascadeMetrics()
    start_time = time.time()

    logger.info(
        "API extraction started",
        extra={"artigo_id": artigo_id, "provider": provider, "action": "extract_api"},
    )

    try:
        # Reutilizar cliente existente ou criar novo
        if client is None:
            ctx = make_context()
            client = LLMClient(ctx)

        # Montar prompt com texto do artigo embutido
        full_prompt = prompt_template.replace("{TEXT}", text[:100000])
        text_content = _build_api_content_blocks(text)

        if images:
            try:
                from . import pdf_vision
            except ImportError:
                import pdf_vision

            provider_kind = (
                client.get_provider_kind(provider)
                if hasattr(client, "get_provider_kind")
                else provider
            )
            if provider_kind == "anthropic":
                image_blocks = pdf_vision.get_images_for_anthropic(images)
            else:
                image_blocks = pdf_vision.get_images_for_openai(images)

            response = client.extract_with_vision(
                images=image_blocks,
                prompt=full_prompt,
                artigo_id=artigo_id,
                provider=provider,
            )
        else:
            response = client.extract_with_hybrid(
                content=text_content,
                prompt=full_prompt,
                artigo_id=artigo_id,
                provider=provider,
            )

        metrics.api_time_ms = (time.time() - start_time) * 1000
        metrics.api_tokens = int(getattr(response, "total_tokens", 0))
        metrics.total_time_ms = metrics.api_time_ms
        metrics.attempts = 1
        metrics.api_cost_estimate = _estimate_api_cost(provider, metrics.api_tokens)

        yaml_content = _extract_yaml_from_response(response)
        return yaml_content, metrics

    except ExtractError:
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise
    except Exception as e:
        logger.error(
            "API extraction error: %s",
            e,
            extra={"artigo_id": artigo_id, "provider": provider, "action": "extract_api"},
        )
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"API extraction failed: {e}") from e


# ============================================================
# Pipeline de Cascata
# ============================================================


def _try_api_only_extraction(
    artigo_id: str,
    text: str,
    prompt_template: str,
    *,
    images: list[Path] | None,
) -> CascadeResult:
    """Executa caminho API-only com tratamento uniforme de falhas."""
    api_provider = _resolve_api_provider(_select_cascade_api_provider())
    api_source = _source_for_api_provider(api_provider)
    try:
        yaml_content, metrics = extract_with_api(
            text,
            prompt_template,
            provider=api_provider,
            images=images,
            artigo_id=artigo_id,
        )
        validation = _validate_yaml(yaml_content, artigo_id)
        confidence = _estimate_confidence(yaml_content, validation)
        return CascadeResult(
            yaml_content=yaml_content,
            source=api_source,
            confidence=confidence,
            validation=validation,
            metrics=metrics,
        )
    except Exception as e:
        return CascadeResult(
            yaml_content="",
            source=api_source,
            confidence=0.0,
            validation=None,
            metrics=CascadeMetrics(),
            success=False,
            error=str(e),
        )


def _try_local_extraction(
    artigo_id: str,
    text: str,
    prompt_template: str,
    *,
    images: list[Path] | None,
    max_local_retries: int,
    confidence_threshold: float,
    total_metrics: CascadeMetrics,
) -> LocalAttemptResult:
    """Executa tentativas locais com validação e repair opcional."""
    result = LocalAttemptResult(
        source=ExtractionSource.LOCAL_OLLAMA_VISION if images else ExtractionSource.LOCAL_OLLAMA
    )

    for attempt in range(max_local_retries):
        try:
            yaml_content, metrics = extract_with_ollama(
                text,
                prompt_template,
                images=images,
                artigo_id=artigo_id,
            )
            total_metrics.local_time_ms += metrics.local_time_ms
            total_metrics.local_tokens += metrics.local_tokens
            total_metrics.attempts += 1

            validation = _validate_yaml(yaml_content, artigo_id)
            confidence = _estimate_confidence(yaml_content, validation)
            result.yaml_content = yaml_content
            result.validation = validation
            result.confidence = confidence

            logger.info(
                "Local attempt %d: confidence=%.2f",
                attempt + 1,
                confidence,
                extra={"artigo_id": artigo_id, "action": "confidence", "attempt": attempt + 1},
            )

            if confidence >= confidence_threshold and validation and validation.is_valid:
                result.accepted = True
                return result

            if validation and not validation.is_valid and attempt < max_local_retries - 1:
                logger.info(
                    "Attempting local repair",
                    extra={"artigo_id": artigo_id, "action": "repair_local"},
                )
                errors = validation.errors[:5]
                repaired_yaml, repair_metrics = repair_with_ollama(
                    yaml_content,
                    errors,
                    artigo_id=artigo_id,
                )
                total_metrics.local_time_ms += repair_metrics.local_time_ms
                total_metrics.local_tokens += repair_metrics.local_tokens
                result.yaml_content = repaired_yaml

        except Exception as e:
            logger.warning(
                "Local attempt %d failed: %s",
                attempt + 1,
                e,
                extra={"artigo_id": artigo_id, "action": "extract_local", "attempt": attempt + 1},
            )

    return result


def _select_best_result(
    local_result: LocalAttemptResult, api_source: ExtractionSource, total_metrics: CascadeMetrics
) -> ExtractionSource:
    """Define a source final quando houve fallback local + API."""
    if total_metrics.local_tokens > 0:
        return ExtractionSource.HYBRID
    return api_source


def _try_api_extraction(
    artigo_id: str,
    text: str,
    prompt_template: str,
    *,
    images: list[Path] | None,
    total_metrics: CascadeMetrics,
    start_time: float,
    local_result: LocalAttemptResult,
) -> CascadeResult:
    """Executa fallback de API e retorna o melhor resultado disponível."""
    api_provider = _resolve_api_provider(_select_cascade_api_provider())
    api_source = _source_for_api_provider(api_provider)
    try:
        yaml_content, api_metrics = extract_with_api(
            text,
            prompt_template,
            provider=api_provider,
            images=images,
            artigo_id=artigo_id,
        )
        total_metrics.api_time_ms = api_metrics.api_time_ms
        total_metrics.api_tokens = api_metrics.api_tokens
        total_metrics.api_cost_estimate = api_metrics.api_cost_estimate

        validation = _validate_yaml(yaml_content, artigo_id)
        confidence = _estimate_confidence(yaml_content, validation)
        total_metrics.total_time_ms = (time.time() - start_time) * 1000

        return CascadeResult(
            yaml_content=yaml_content,
            source=_select_best_result(local_result, api_source, total_metrics),
            confidence=confidence,
            validation=validation,
            metrics=total_metrics,
        )
    except Exception as e:
        total_metrics.total_time_ms = (time.time() - start_time) * 1000
        return CascadeResult(
            yaml_content=local_result.yaml_content,
            source=local_result.source,
            confidence=local_result.confidence,
            validation=local_result.validation,
            metrics=total_metrics,
            success=False,
            error=f"API escalation failed: {e}",
        )


def extract_cascade(
    artigo_id: str,
    text: str,
    prompt_template: str,
    *,
    strategy: Literal["local_first", "api_first", "local_only", "api_only"] | None = None,
    images: list[Path] | None = None,
    confidence_threshold: float | None = None,
    max_local_retries: int = 2,
) -> CascadeResult:
    """
    Extrai CIMO usando estratégia de cascata.

    Estratégias:
    - local_first: Tenta local, escala para API se necessário
    - api_first: Usa API diretamente
    - local_only: Apenas local, falha se não conseguir
    - api_only: Apenas API

    Args:
        artigo_id: ID do artigo
        text: Texto do artigo
        prompt_template: Template do prompt de extração
        strategy: Estratégia de extração
        images: Imagens opcionais para modelo vision
        confidence_threshold: Limite de confiança para aceitar resultado local
        max_local_retries: Máximo de tentativas locais antes de escalar

    Returns:
        CascadeResult com extração e métricas
    """
    strategy = cast(
        Literal["local_first", "api_first", "local_only", "api_only"],
        strategy or local_config.EXTRACTION_STRATEGY,
    )
    resolved_confidence_threshold = confidence_threshold
    if resolved_confidence_threshold is None:
        resolved_confidence_threshold = float(local_config.LOCAL_CONFIDENCE_THRESHOLD)

    total_metrics = CascadeMetrics()
    start_time = time.time()

    logger.info(
        "Cascade extraction started",
        extra={"artigo_id": artigo_id, "action": "cascade_step", "strategy": strategy},
    )

    if strategy == "api_only":
        return _try_api_only_extraction(
            artigo_id,
            text,
            prompt_template,
            images=images,
        )

    local_result = _try_local_extraction(
        artigo_id,
        text,
        prompt_template,
        images=images,
        max_local_retries=max_local_retries,
        confidence_threshold=resolved_confidence_threshold,
        total_metrics=total_metrics,
    )

    if local_result.accepted:
        total_metrics.total_time_ms = (time.time() - start_time) * 1000
        return CascadeResult(
            yaml_content=local_result.yaml_content,
            source=local_result.source,
            confidence=local_result.confidence,
            validation=local_result.validation,
            metrics=total_metrics,
        )

    if strategy == "local_only":
        total_metrics.total_time_ms = (time.time() - start_time) * 1000

        return CascadeResult(
            yaml_content=local_result.yaml_content,
            source=local_result.source,
            confidence=local_result.confidence,
            validation=local_result.validation,
            metrics=total_metrics,
            success=local_result.confidence >= 0.5,
        )

    logger.info(
        "Escalating to API, confidence=%.2f",
        local_result.confidence,
        extra={"artigo_id": artigo_id, "action": "fallback"},
    )
    total_metrics.escalated = True
    total_metrics.escalation_reason = (
        f"Low confidence ({local_result.confidence:.2f}) or validation failed"
    )

    return _try_api_extraction(
        artigo_id,
        text,
        prompt_template,
        images=images,
        total_metrics=total_metrics,
        start_time=start_time,
        local_result=local_result,
    )


# ============================================================
# Funções Auxiliares
# ============================================================


def _extract_yaml_block(content: str) -> str:
    """Extrai bloco YAML de uma resposta."""
    # Tentar extrair de code block
    if "```yaml" in content:
        start = content.find("```yaml") + 7
        end = content.find("```", start)
        if end > start:
            return content[start:end].strip()

    if "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        if end > start:
            return content[start:end].strip()

    return content.strip()


def _validate_yaml(yaml_content: str, artigo_id: str) -> ValidationResult | None:
    """Valida YAML extraído."""
    try:
        return validate_yaml(yaml_content)
    except Exception as e:
        logger.warning(
            "Validation failed: %s",
            e,
            extra={"artigo_id": artigo_id, "action": "validate"},
        )
        return None


def _estimate_confidence(yaml_content: str, validation: ValidationResult | None) -> float:
    """
    Estima confiança da extração com scoring granular.

    Fatores ponderados:
    - Validação (0.25): passou/falhou + penalidade proporcional a erros/warnings
    - Campos obrigatórios (0.25): presença dos campos-chave do schema CIMO
    - Qualidade de quotes (0.20): quantidade, comprimento, referências de página
    - Narrativas (0.15): campos multi-linha com conteúdo substancial
    - Tamanho e formato (0.10): YAML com tamanho razoável e char '→' em Mecanismo
    - Penalidades: valores "NR" reduzem confiança
    """
    if not yaml_content:
        return 0.0

    score = 0.0

    # --- 1. Validação (peso 0.25) ---
    validation_score = 0.5  # base neutra se sem validação
    if validation:
        if validation.is_valid:
            validation_score = 1.0
        else:
            n_errors = len(validation.errors)
            # Penalidade regressiva: 1 erro = 0.3, 2 = 0.15, 5+ = 0.0
            validation_score = max(0.0, 0.5 - 0.1 * min(n_errors, 5))
        # Warnings reduzem levemente
        validation_score -= 0.04 * min(len(validation.warnings), 5)
    score += max(0.0, validation_score) * 0.25

    # --- 2. Campos obrigatórios (peso 0.25) ---
    required_fields = [
        "ArtigoID",
        "ClasseIA",
        "Mecanismo_Estruturado",
        "Quotes",
        "ProblemaNegócio_Contexto",
        "Intervenção_Descrição",
        "ResultadoTipo",
        "NívelEvidência",
    ]
    fields_found = sum(1 for f in required_fields if f in yaml_content)
    fields_ratio = fields_found / len(required_fields)
    score += fields_ratio * 0.25

    # --- 3. Qualidade de quotes (peso 0.20) ---
    quote_score = 0.0
    quote_count = yaml_content.count("QuoteID:")
    if quote_count >= 5:
        quote_score += 0.5
    elif quote_count >= 3:
        quote_score += 0.3
    elif quote_count >= 1:
        quote_score += 0.1

    # Quotes com referência de página
    page_refs = yaml_content.count('Página: "p.')
    if page_refs >= 3:
        quote_score += 0.3
    elif page_refs >= 1:
        quote_score += 0.15

    # Diversidade de tipos de quote
    quote_types = ["Contexto", "Intervenção", "Mecanismo", "Outcome", "Limitação"]
    types_found = sum(1 for t in quote_types if f'TipoQuote: "{t}"' in yaml_content)
    if types_found >= 3:
        quote_score += 0.2
    elif types_found >= 2:
        quote_score += 0.1

    score += min(1.0, quote_score) * 0.20

    # --- 4. Narrativas substanciais (peso 0.15) ---
    narrative_fields = [
        "ProblemaNegócio_Contexto",
        "Intervenção_Descrição",
        "Dados_Descrição",
        "Mecanismo_Declarado",
        "Mecanismo_Inferido",
    ]
    narratives_present = sum(1 for f in narrative_fields if f in yaml_content)
    narrative_ratio = narratives_present / len(narrative_fields)
    score += narrative_ratio * 0.15

    # --- 5. Tamanho e formato (peso 0.10) ---
    format_score = 0.0
    if 1000 < len(yaml_content) < 20000:
        format_score += 0.5
    elif 500 < len(yaml_content) <= 1000:
        format_score += 0.25

    # Mecanismo_Estruturado com cadeia '→'
    if "→" in yaml_content:
        format_score += 0.3

    # Prefixo INFERIDO: presente
    if "INFERIDO:" in yaml_content:
        format_score += 0.2

    score += min(1.0, format_score) * 0.10

    # --- 6. Penalidades por valores NR ---
    critical_nr_fields = ["ClasseIA", "ResultadoTipo", "Maturidade", "TarefaAnalítica"]
    for field in critical_nr_fields:
        # Detecta padrões como 'ClasseIA: "NR"' ou "ClasseIA: NR"
        if f'{field}: "NR"' in yaml_content or f"{field}: NR" in yaml_content:
            score -= 0.03

    return max(0.0, min(1.0, score))


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    print("=== Cascade Pipeline Test ===\n")

    # Testar com texto simples
    test_text = """
    This paper presents an AI-based approach for supply chain risk management
    in a complex industrial network. We use machine learning to predict disruptions.
    The results show a 25% improvement in prediction accuracy.
    """

    test_prompt = """Extract CIMO information from the following text:

{TEXT}

Return as YAML with fields: Contexto, Intervencao, Mecanismo, Outcome
"""

    print("Testando extração local...")
    try:
        result = extract_cascade(
            "TEST_001",
            test_text,
            test_prompt,
            strategy="local_only",
        )

        print(f"  Source: {result.source.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Success: {result.success}")
        print(f"  Local tokens: {result.metrics.local_tokens}")
        print(f"  Time: {result.metrics.total_time_ms:.0f}ms")

        if result.yaml_content:
            print("\n  YAML Preview:")
            print("  " + result.yaml_content[:200].replace("\n", "\n  "))

    except Exception as e:
        print(f"  Erro: {e}")
