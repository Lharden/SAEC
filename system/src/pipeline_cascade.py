"""Pipeline de extração em cascata com estratégia cloud/local + fallback de API."""

from __future__ import annotations

import logging
import time
import importlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

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
    has_openai = not _is_placeholder_api_key(getattr(llm_config, "OPENAI_API_KEY", ""))
    has_anthropic = not _is_placeholder_api_key(
        getattr(llm_config, "ANTHROPIC_API_KEY", "")
    )
    preferred = (preferred_provider or "").strip().lower()
    if preferred == "openai" and has_openai:
        return "openai"
    if preferred == "anthropic" and has_anthropic:
        return "anthropic"
    if preferred == "openai" and has_anthropic:
        logger.warning(
            "OpenAI indisponivel para cascade API; usando Anthropic",
            extra={"action": "resolve_api_provider", "provider": "anthropic"},
        )
        return "anthropic"
    if preferred == "anthropic" and has_openai:
        logger.warning(
            "Anthropic indisponivel para cascade API; usando OpenAI",
            extra={"action": "resolve_api_provider", "provider": "openai"},
        )
        return "openai"

    if has_openai:
        return "openai"
    if has_anthropic:
        return "anthropic"
    return "anthropic"


def _select_cascade_api_provider() -> str:
    configured = (
        str(getattr(llm_config, "PROVIDER_CASCADE_API", "auto")).strip().lower()
    )
    if configured in {"anthropic", "openai"}:
        return configured
    primary = str(getattr(llm_config, "PRIMARY_PROVIDER", "ollama")).strip().lower()
    return primary


def _source_for_api_provider(provider: str) -> ExtractionSource:
    if provider == "openai":
        return ExtractionSource.API_OPENAI
    return ExtractionSource.API_ANTHROPIC


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
            "Ollama extraction error: %s", e,
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
            "Ollama repair error: %s", e,
            extra={"artigo_id": artigo_id, "model": model, "action": "repair_local"},
        )
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"Ollama repair failed: {e}") from e


# ============================================================
# Funções de Extração API
# ============================================================


def extract_with_api(
    text: str,
    prompt_template: str,
    *,
    provider: Literal["anthropic", "openai"] = "anthropic",
    images: list[Path] | None = None,
    artigo_id: str = "",
    client: object | None = None,
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

        # Conteúdo do artigo como blocos na mensagem do usuário
        text_content: list[dict] = [{"type": "text", "text": text[:100000]}]

        if images:
            try:
                from . import pdf_vision
            except ImportError:
                import pdf_vision

            if provider == "anthropic":
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
        metrics.api_tokens = (
            getattr(response, "total_tokens", 0)
            if hasattr(response, "total_tokens")
            else 0
        )
        metrics.total_time_ms = metrics.api_time_ms
        metrics.attempts = 1

        # Estimar custo
        if provider == "anthropic":
            metrics.api_cost_estimate = metrics.api_tokens * 0.000009
        else:
            metrics.api_cost_estimate = metrics.api_tokens * 0.00001

        # Extrair YAML do resultado
        if isinstance(response, str):
            yaml_content = _extract_yaml_block(response)
        elif hasattr(response, "content"):
            yaml_content = _extract_yaml_block(response.content)
        else:
            yaml_content = _extract_yaml_block(str(response))

        return yaml_content, metrics

    except ExtractError:
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise
    except Exception as e:
        logger.error(
            "API extraction error: %s", e,
            extra={"artigo_id": artigo_id, "provider": provider, "action": "extract_api"},
        )
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"API extraction failed: {e}") from e


# ============================================================
# Pipeline de Cascata
# ============================================================


def extract_cascade(
    artigo_id: str,
    text: str,
    prompt_template: str,
    *,
    strategy: Literal["local_first", "api_first", "local_only", "api_only"]
    | None = None,
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

    # ========================================
    # Estratégia: API Only
    # ========================================
    if strategy == "api_only":
        api_provider = _resolve_api_provider(_select_cascade_api_provider())
        api_source = _source_for_api_provider(api_provider)
        try:
            yaml_content, metrics = extract_with_api(
                text,
                prompt_template,
                provider=cast(Literal["anthropic", "openai"], api_provider),
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
                metrics=total_metrics,
                success=False,
                error=str(e),
            )

    # ========================================
    # Estratégia: Local First ou Local Only
    # ========================================
    yaml_content = ""
    validation = None
    confidence = 0.0
    source = ExtractionSource.LOCAL_OLLAMA

    for attempt in range(max_local_retries):
        try:
            # Tentar extração local
            if images:
                source = ExtractionSource.LOCAL_OLLAMA_VISION

            yaml_content, metrics = extract_with_ollama(
                text,
                prompt_template,
                images=images,
                artigo_id=artigo_id,
            )

            total_metrics.local_time_ms += metrics.local_time_ms
            total_metrics.local_tokens += metrics.local_tokens
            total_metrics.attempts += 1

            # Validar
            validation = _validate_yaml(yaml_content, artigo_id)
            confidence = _estimate_confidence(yaml_content, validation)

            logger.info(
                "Local attempt %d: confidence=%.2f", attempt + 1, confidence,
                extra={"artigo_id": artigo_id, "action": "confidence", "attempt": attempt + 1},
            )

            # Aceitar se passar no threshold
            if (
                confidence >= resolved_confidence_threshold
                and validation
                and validation.is_valid
            ):
                total_metrics.total_time_ms = (time.time() - start_time) * 1000

                return CascadeResult(
                    yaml_content=yaml_content,
                    source=source,
                    confidence=confidence,
                    validation=validation,
                    metrics=total_metrics,
                )

            # Tentar repair se tiver erros
            if (
                validation
                and not validation.is_valid
                and attempt < max_local_retries - 1
            ):
                logger.info(
                    "Attempting local repair",
                    extra={"artigo_id": artigo_id, "action": "repair_local"},
                )
                errors = validation.errors[:5]  # errors já é list[str]
                yaml_content, repair_metrics = repair_with_ollama(
                    yaml_content,
                    errors,
                    artigo_id=artigo_id,
                )
                total_metrics.local_time_ms += repair_metrics.local_time_ms
                total_metrics.local_tokens += repair_metrics.local_tokens

        except Exception as e:
            logger.warning(
                "Local attempt %d failed: %s", attempt + 1, e,
                extra={"artigo_id": artigo_id, "action": "extract_local", "attempt": attempt + 1},
            )

    # ========================================
    # Escalar para API (se local_first)
    # ========================================
    if strategy == "local_only":
        total_metrics.total_time_ms = (time.time() - start_time) * 1000

        return CascadeResult(
            yaml_content=yaml_content,
            source=source,
            confidence=confidence,
            validation=validation,
            metrics=total_metrics,
            success=confidence >= 0.5,  # Aceitar com confiança moderada
        )

    # Escalar para API
    logger.info(
        "Escalating to API, confidence=%.2f", confidence,
        extra={"artigo_id": artigo_id, "action": "fallback"},
    )
    total_metrics.escalated = True
    total_metrics.escalation_reason = (
        f"Low confidence ({confidence:.2f}) or validation failed"
    )

    try:
        api_provider = _resolve_api_provider(_select_cascade_api_provider())
        api_source = _source_for_api_provider(api_provider)
        yaml_content, api_metrics = extract_with_api(
            text,
            prompt_template,
            provider=cast(Literal["anthropic", "openai"], api_provider),
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
            source=ExtractionSource.HYBRID
            if total_metrics.local_tokens > 0
            else api_source,
            confidence=confidence,
            validation=validation,
            metrics=total_metrics,
        )

    except Exception as e:
        total_metrics.total_time_ms = (time.time() - start_time) * 1000

        return CascadeResult(
            yaml_content=yaml_content,  # Retorna último YAML local
            source=source,
            confidence=confidence,
            validation=validation,
            metrics=total_metrics,
            success=False,
            error=f"API escalation failed: {e}",
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
            "Validation failed: %s", e,
            extra={"artigo_id": artigo_id, "action": "validate"},
        )
        return None


def _estimate_confidence(
    yaml_content: str, validation: ValidationResult | None
) -> float:
    """
    Estima confiança da extração.

    Fatores:
    - Validação passou/falhou
    - Número de erros/warnings
    - Tamanho do YAML
    - Presença de campos obrigatórios
    """
    if not yaml_content:
        return 0.0

    confidence = 0.5  # Base

    # Validação
    if validation:
        if validation.is_valid:
            confidence += 0.3
        else:
            confidence -= 0.1 * min(len(validation.errors), 5)

        # Warnings
        confidence -= 0.05 * min(len(validation.warnings), 5)

    # Tamanho razoável
    if 500 < len(yaml_content) < 20000:
        confidence += 0.1

    # Campos obrigatórios do schema CIMO presentes
    required_fields = [
        "ArtigoID", "ClasseIA", "Mecanismo_Estruturado", "Quotes",
        "ProblemaNegócio_Contexto", "Intervenção_Descrição",
        "ResultadoTipo", "NívelEvidência",
    ]
    for field in required_fields:
        if field in yaml_content:
            confidence += 0.0125

    return max(0.0, min(1.0, confidence))


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
            print(f"\n  YAML Preview:")
            print("  " + result.yaml_content[:200].replace("\n", "\n  "))

    except Exception as e:
        print(f"  Erro: {e}")
