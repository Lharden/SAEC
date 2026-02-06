"""
Pipeline de Extração em Cascata.

Estratégia local-first para economia de tokens:
1. Tenta extração com modelo local (Ollama)
2. Valida resultado
3. Se falhar ou baixa confiança, escala para API

Economia estimada: 60-80% em tokens de API.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

try:
    from .config import paths, llm_config, extraction_config, local_config
    from .exceptions import ExtractError, LLMError
    from .validators import ValidationResult, validate_yaml
except ImportError:  # pragma: no cover - standalone usage
    from config import paths, llm_config, extraction_config, local_config
    from exceptions import ExtractError, LLMError
    from validators import ValidationResult, validate_yaml

logger = logging.getLogger(__name__)


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
        if self.source in [ExtractionSource.LOCAL_OLLAMA, ExtractionSource.LOCAL_OLLAMA_VISION]:
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

    # Escolher modelo
    if images:
        model = model or local_config.OLLAMA_EXTRACTION_MODEL
        logger.info(f"[{artigo_id}] Extração vision com {model}")
    else:
        model = model or local_config.OLLAMA_REPAIR_MODEL
        logger.info(f"[{artigo_id}] Extração texto com {model}")

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

    except Exception as e:
        logger.error(f"[{artigo_id}] Erro na extração Ollama: {e}")
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"Ollama extraction failed: {e}")


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
    logger.info(f"[{artigo_id}] Repair com {model}")

    try:
        prompt = f"""Corrija o seguinte YAML baseado nos erros de validação.

ERROS:
{chr(10).join(f'- {e}' for e in validation_errors)}

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

    except Exception as e:
        logger.error(f"[{artigo_id}] Erro no repair Ollama: {e}")
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"Ollama repair failed: {e}")


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
) -> tuple[str, CascadeMetrics]:
    """
    Extrai CIMO usando API (Anthropic/OpenAI).

    Args:
        text: Texto do artigo
        prompt_template: Template do prompt
        provider: Provider da API
        images: Imagens opcionais
        artigo_id: ID do artigo

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

    logger.info(f"[{artigo_id}] Extração API com {provider}")

    try:
        # Criar contexto e cliente
        ctx = make_context()
        client = LLMClient(ctx)

        # Montar prompt
        full_prompt = prompt_template.replace("{TEXT}", text[:100000])

        # Extrair usando método existente (assinaturas corretas)
        if images:
            response = client.extract_with_vision(
                images=images,
                prompt=full_prompt,
                artigo_id=artigo_id,
                provider=provider,
            )
        else:
            # Usar extract_with_hybrid que é o método principal
            response = client.extract_with_hybrid(
                content=[],
                prompt=full_prompt,
                artigo_id=artigo_id,
                provider=provider,
            )

        metrics.api_time_ms = (time.time() - start_time) * 1000
        metrics.api_tokens = getattr(response, 'total_tokens', 0) if hasattr(response, 'total_tokens') else 0
        metrics.total_time_ms = metrics.api_time_ms
        metrics.attempts = 1

        # Estimar custo
        if provider == "anthropic":
            metrics.api_cost_estimate = (metrics.api_tokens * 0.000009)
        else:
            metrics.api_cost_estimate = (metrics.api_tokens * 0.00001)

        # Extrair YAML do resultado
        if isinstance(response, str):
            yaml_content = _extract_yaml_block(response)
        elif hasattr(response, 'content'):
            yaml_content = _extract_yaml_block(response.content)
        else:
            yaml_content = _extract_yaml_block(str(response))

        return yaml_content, metrics

    except Exception as e:
        logger.error(f"[{artigo_id}] Erro na extração API: {e}")
        metrics.total_time_ms = (time.time() - start_time) * 1000
        raise ExtractError(f"API extraction failed: {e}")


# ============================================================
# Pipeline de Cascata
# ============================================================

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
    strategy = strategy or local_config.EXTRACTION_STRATEGY
    confidence_threshold = confidence_threshold or local_config.LOCAL_CONFIDENCE_THRESHOLD

    total_metrics = CascadeMetrics()
    start_time = time.time()

    logger.info(f"[{artigo_id}] Iniciando extração cascata (strategy={strategy})")

    # ========================================
    # Estratégia: API Only
    # ========================================
    if strategy == "api_only":
        try:
            yaml_content, metrics = extract_with_api(
                text, prompt_template,
                provider=llm_config.PRIMARY_PROVIDER,
                images=images,
                artigo_id=artigo_id,
            )

            validation = _validate_yaml(yaml_content, artigo_id)
            confidence = _estimate_confidence(yaml_content, validation)

            return CascadeResult(
                yaml_content=yaml_content,
                source=ExtractionSource.API_ANTHROPIC,
                confidence=confidence,
                validation=validation,
                metrics=metrics,
            )

        except Exception as e:
            return CascadeResult(
                yaml_content="",
                source=ExtractionSource.API_ANTHROPIC,
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
                text, prompt_template,
                images=images,
                artigo_id=artigo_id,
            )

            total_metrics.local_time_ms += metrics.local_time_ms
            total_metrics.local_tokens += metrics.local_tokens
            total_metrics.attempts += 1

            # Validar
            validation = _validate_yaml(yaml_content, artigo_id)
            confidence = _estimate_confidence(yaml_content, validation)

            logger.info(f"[{artigo_id}] Local attempt {attempt+1}: confidence={confidence:.2f}")

            # Aceitar se passar no threshold
            if confidence >= confidence_threshold and validation and validation.is_valid:
                total_metrics.total_time_ms = (time.time() - start_time) * 1000

                return CascadeResult(
                    yaml_content=yaml_content,
                    source=source,
                    confidence=confidence,
                    validation=validation,
                    metrics=total_metrics,
                )

            # Tentar repair se tiver erros
            if validation and not validation.is_valid and attempt < max_local_retries - 1:
                logger.info(f"[{artigo_id}] Tentando repair local...")
                errors = validation.errors[:5]  # errors já é list[str]
                yaml_content, repair_metrics = repair_with_ollama(
                    yaml_content, errors,
                    artigo_id=artigo_id,
                )
                total_metrics.local_time_ms += repair_metrics.local_time_ms
                total_metrics.local_tokens += repair_metrics.local_tokens

        except Exception as e:
            logger.warning(f"[{artigo_id}] Local attempt {attempt+1} failed: {e}")

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
    logger.info(f"[{artigo_id}] Escalando para API (confidence={confidence:.2f})")
    total_metrics.escalated = True
    total_metrics.escalation_reason = f"Low confidence ({confidence:.2f}) or validation failed"

    try:
        yaml_content, api_metrics = extract_with_api(
            text, prompt_template,
            provider=llm_config.PRIMARY_PROVIDER,
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
            source=ExtractionSource.HYBRID if total_metrics.local_tokens > 0 else ExtractionSource.API_ANTHROPIC,
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
        logger.warning(f"[{artigo_id}] Validação falhou: {e}")
        return None


def _estimate_confidence(yaml_content: str, validation: ValidationResult | None) -> float:
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

    # Campos obrigatórios presentes
    required_fields = ["ArtigoID", "Contexto", "Intervencao", "Outcome"]
    for field in required_fields:
        if field in yaml_content:
            confidence += 0.025

    return max(0.0, min(1.0, confidence))


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    print("=== Cascade Pipeline Test ===\n")

    # Testar com texto simples
    test_text = """
    This paper presents an AI-based approach for supply chain risk management
    in the oil and gas industry. We use machine learning to predict disruptions.
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
