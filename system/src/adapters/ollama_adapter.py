"""
Adapter unificado para modelos Ollama.

Fornece interface consistente para:
- Geração de texto (modelos cloud/local)
- Geração com visão (modelos multimodais)
- OCR especializado (glm-ocr)
- Embeddings (nomic-embed-text-v2-moe)
- Reranking (bge-reranker-v2-m3)
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Union, Sequence

import ollama
from PIL import Image
from PIL.Image import Image as PILImage

try:
    from ..exceptions import LLMError
except ImportError:  # pragma: no cover - standalone usage
    from exceptions import LLMError

logger = logging.getLogger(__name__)


def _int_or_zero(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _duration_ms_from_ns(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(int(value)) / 1_000_000
    if isinstance(value, (int, float, str)):
        try:
            return float(value) / 1_000_000
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(str(value)) / 1_000_000
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# Data Classes
# ============================================================


@dataclass
class OllamaResponse:
    """Resposta de um modelo Ollama."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    load_duration_ms: float = 0.0
    eval_duration_ms: float = 0.0


@dataclass
class OllamaModel:
    """Metadados de um modelo Ollama."""

    name: str
    size_gb: float
    family: str
    parameter_size: str
    quantization: str
    capabilities: list[str] = field(default_factory=list)


@dataclass
class EmbeddingResult:
    """Resultado de embedding."""

    embedding: list[float]
    model: str
    dimensions: int
    processing_time_ms: float


@dataclass
class RerankResult:
    """Resultado de reranking."""

    rankings: list[tuple[int, float]]  # (index, score)
    model: str
    processing_time_ms: float


# ============================================================
# Modelo Padrões por Tarefa
# ============================================================

DEFAULT_MODELS = {
    "cloud": "glm-4.7:cloud",  # Cloud proxy - extração/repair (sem VRAM)
    "cloud_fallback": "kimi-k2.5:cloud",  # Cloud fallback (sem VRAM)
    "text": "qwen3-vl:8b",  # 6.1 GB - cabe em GPU 10GB
    "vision": "qwen3-vl:8b",  # 6.1 GB - visão local (cabe em GPU 10GB)
    "vision_fast": "qwen3-vl:8b",  # 6.1 GB - mesmo modelo (GPU limitada)
    "ocr": "glm-ocr:latest",  # 2.2 GB - OCR especializado
    "embedding": "nomic-embed-text-v2-moe",  # 0.9 GB - embeddings (note: sem :latest)
    "reranker": "qllama/bge-reranker-v2-m3:q4_k_m",  # 0.4 GB - reranking
}


# ============================================================
# Funções de Verificação
# ============================================================


def is_ollama_available() -> bool:
    """Verifica se Ollama está rodando."""
    try:
        ollama.list()
        return True
    except Exception:
        return False


def list_models() -> list[OllamaModel]:
    """Lista todos os modelos disponíveis no Ollama."""
    try:
        response = ollama.list()
        models = []

        # Nova API retorna objeto com atributo .models
        if hasattr(response, "models"):
            model_list = response.models or []
        elif isinstance(response, dict):
            model_list = response.get("models", [])
        else:
            model_list = []

        for model in model_list:
            # Suportar tanto objeto quanto dict
            if hasattr(model, "model"):
                name = str(getattr(model, "model", "") or "")
                size_bytes = getattr(model, "size", 0)
                details = getattr(model, "details", None)
                family = str(getattr(details, "family", "unknown") or "unknown") if details else "unknown"
                param_size = (
                    str(getattr(details, "parameter_size", "unknown") or "unknown")
                    if details
                    else "unknown"
                )
                quant = (
                    str(getattr(details, "quantization_level", "unknown") or "unknown")
                    if details
                    else "unknown"
                )
            else:
                name = str(model.get("name", "") or "")
                size_bytes = model.get("size", 0)
                details = model.get("details", {})
                family = str(details.get("family", "unknown") or "unknown")
                param_size = str(
                    details.get("parameter_size", "unknown") or "unknown"
                )
                quant = str(
                    details.get("quantization_level", "unknown") or "unknown"
                )

            # Determinar capacidades baseado no nome
            capabilities = ["text"]
            name_lower = name.lower()
            if "vl" in name_lower or "vision" in name_lower:
                capabilities.append("vision")
            if "embed" in name_lower:
                capabilities = ["embedding"]
            if "rerank" in name_lower:
                capabilities = ["reranking"]
            if "ocr" in name_lower:
                capabilities.append("ocr")

            models.append(
                OllamaModel(
                    name=name,
                    size_gb=size_bytes / (1024**3),
                    family=family,
                    parameter_size=param_size,
                    quantization=quant,
                    capabilities=capabilities,
                )
            )

        return models
    except Exception as e:
        logger.error(
            "Error listing Ollama models: %s", e,
            extra={"action": "list"},
        )
        return []


def check_model_available(model_name: str) -> bool:
    """Verifica se um modelo específico está disponível."""
    models = list_models()
    model_base = model_name.split(":")[0]
    for m in models:
        # Match exato ou por prefixo
        if m.name == model_name:
            return True
        if m.name.startswith(model_base):
            return True
        # Match sem :latest
        if model_name.endswith(":latest") and m.name == model_base:
            return True
        if m.name.startswith(model_name):
            return True
    return False


def get_model_for_task(
    task: Literal[
        "cloud",
        "cloud_fallback",
        "text",
        "vision",
        "vision_fast",
        "ocr",
        "embedding",
        "reranker",
    ],
) -> str:
    """Retorna o modelo padrão para uma tarefa."""
    return DEFAULT_MODELS.get(task, DEFAULT_MODELS["text"])


# ============================================================
# Funções de Geração
# ============================================================


def generate_text(
    prompt: str,
    *,
    model: str | None = None,
    system: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout: float = 300.0,
) -> OllamaResponse:
    """
    Gera texto com modelo Ollama.

    Args:
        prompt: Prompt do usuário
        model: Nome do modelo (padrão: DEFAULT_MODELS["text"])
        system: Prompt de sistema opcional
        temperature: Temperatura de sampling
        max_tokens: Máximo de tokens na resposta
        timeout: Timeout em segundos

    Returns:
        OllamaResponse com texto gerado

    Raises:
        LLMError: Se geração falhar
    """
    model = model or DEFAULT_MODELS["text"]

    try:
        start_time = time.time()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )

        elapsed_ms = (time.time() - start_time) * 1000
        prompt_tokens = _int_or_zero(response.get("prompt_eval_count", 0))
        completion_tokens = _int_or_zero(response.get("eval_count", 0))

        return OllamaResponse(
            content=response["message"]["content"],
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            total_duration_ms=_duration_ms_from_ns(response.get("total_duration", 0)),
            load_duration_ms=_duration_ms_from_ns(response.get("load_duration", 0)),
            eval_duration_ms=elapsed_ms,
        )

    except Exception as e:
        logger.error(
            "Ollama generation error: %s", e,
            extra={"model": model, "action": "generate"},
        )
        raise LLMError(
            f"Ollama generation failed: {e}", provider="ollama", retriable=True
        )


def generate_vision(
    prompt: str,
    images: Sequence[Union[Path, str, bytes, PILImage]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 8000,
    timeout: float = 600.0,
) -> OllamaResponse:
    """
    Gera texto com modelo de visão (multimodal).

    Args:
        prompt: Prompt do usuário
        images: Lista de imagens (paths, base64, bytes ou PIL Image)
        model: Nome do modelo (padrão: DEFAULT_MODELS["vision"])
        temperature: Temperatura de sampling
        max_tokens: Máximo de tokens na resposta
        timeout: Timeout em segundos

    Returns:
        OllamaResponse com texto gerado

    Raises:
        LLMError: Se geração falhar
    """
    model = model or DEFAULT_MODELS["vision"]

    try:
        start_time = time.time()

        # Converter imagens para base64
        image_data = []
        for img in images:
            if isinstance(img, Path):
                with open(img, "rb") as f:
                    image_data.append(base64.b64encode(f.read()).decode("utf-8"))
            elif isinstance(img, bytes):
                image_data.append(base64.b64encode(img).decode("utf-8"))
            elif isinstance(img, PILImage):
                import io

                buffer = io.BytesIO()
                pil_image: PILImage = img
                pil_image.save(buffer, format="PNG")
                image_data.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
            elif isinstance(img, str):
                # Assume já é base64
                image_data.append(img)

        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": image_data,
                }
            ],
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )

        elapsed_ms = (time.time() - start_time) * 1000
        prompt_tokens = _int_or_zero(response.get("prompt_eval_count", 0))
        completion_tokens = _int_or_zero(response.get("eval_count", 0))

        return OllamaResponse(
            content=response["message"]["content"],
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            total_duration_ms=_duration_ms_from_ns(response.get("total_duration", 0)),
            load_duration_ms=_duration_ms_from_ns(response.get("load_duration", 0)),
            eval_duration_ms=elapsed_ms,
        )

    except Exception as e:
        logger.error(
            "Ollama vision generation error: %s", e,
            extra={"model": model, "action": "vision"},
        )
        raise LLMError(
            f"Ollama vision generation failed: {e}", provider="ollama", retriable=True
        )


def generate_ocr(
    image: Union[Path, bytes, Image.Image],
    *,
    model: str | None = None,
    prompt: str = "Extract all text from this image. Return only the extracted text, nothing else.",
) -> OllamaResponse:
    """
    Extrai texto de imagem usando modelo OCR especializado.

    Args:
        image: Imagem para OCR
        model: Modelo OCR (padrão: glm-ocr)
        prompt: Prompt customizado

    Returns:
        OllamaResponse com texto extraído
    """
    model = model or DEFAULT_MODELS["ocr"]
    return generate_vision(
        prompt, [image], model=model, temperature=0.1, max_tokens=4096
    )


# ============================================================
# Funções de Embedding e Reranking
# ============================================================


def generate_embedding(
    text: str,
    *,
    model: str | None = None,
) -> EmbeddingResult:
    """
    Gera embedding de texto.

    Args:
        text: Texto para gerar embedding
        model: Modelo de embedding (padrão: nomic-embed-text-v2-moe)

    Returns:
        EmbeddingResult com vetor de embedding
    """
    model = model or DEFAULT_MODELS["embedding"]

    try:
        start_time = time.time()

        response = ollama.embed(
            model=model,
            input=text,
        )

        elapsed_ms = (time.time() - start_time) * 1000
        embedding = response["embeddings"][0]

        return EmbeddingResult(
            embedding=embedding,
            model=model,
            dimensions=len(embedding),
            processing_time_ms=elapsed_ms,
        )

    except Exception as e:
        logger.error(
            "Ollama embedding error: %s", e,
            extra={"model": model, "action": "embed"},
        )
        raise LLMError(
            f"Ollama embedding failed: {e}", provider="ollama", retriable=True
        )


def generate_embeddings_batch(
    texts: list[str],
    *,
    model: str | None = None,
) -> list[EmbeddingResult]:
    """
    Gera embeddings em batch.

    Args:
        texts: Lista de textos
        model: Modelo de embedding

    Returns:
        Lista de EmbeddingResult
    """
    model = model or DEFAULT_MODELS["embedding"]

    try:
        start_time = time.time()

        response = ollama.embed(
            model=model,
            input=texts,
        )

        elapsed_ms = (time.time() - start_time) * 1000
        elapsed_per_text = elapsed_ms / len(texts)

        results = []
        for emb in response["embeddings"]:
            results.append(
                EmbeddingResult(
                    embedding=emb,
                    model=model,
                    dimensions=len(emb),
                    processing_time_ms=elapsed_per_text,
                )
            )

        return results

    except Exception as e:
        logger.error(
            "Ollama batch embedding error: %s", e,
            extra={"model": model, "action": "embed"},
        )
        raise LLMError(
            f"Ollama batch embedding failed: {e}", provider="ollama", retriable=True
        )


def rerank_passages(
    query: str,
    passages: list[str],
    *,
    model: str | None = None,
    top_k: int = 5,
) -> RerankResult:
    """
    Reordena passagens por relevância à query.

    Nota: BGE-reranker não tem suporte nativo no Ollama.
    Implementação usa embedding similarity como fallback.

    Args:
        query: Query de busca
        passages: Lista de passagens para reordenar
        model: Modelo de reranking
        top_k: Número de resultados a retornar

    Returns:
        RerankResult com rankings ordenados por relevância
    """
    # Fallback: usar similaridade de embeddings
    model = model or DEFAULT_MODELS["embedding"]

    try:
        start_time = time.time()

        # Gerar embeddings
        query_emb = generate_embedding(query, model=model)
        passage_embs = generate_embeddings_batch(passages, model=model)

        # Calcular similaridade cosseno
        import math

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

        scores = []
        for i, emb in enumerate(passage_embs):
            score = cosine_similarity(query_emb.embedding, emb.embedding)
            scores.append((i, score))

        # Ordenar por score decrescente
        scores.sort(key=lambda x: x[1], reverse=True)

        elapsed_ms = (time.time() - start_time) * 1000

        return RerankResult(
            rankings=scores[:top_k],
            model=model,
            processing_time_ms=elapsed_ms,
        )

    except Exception as e:
        logger.error(
            "Reranking error: %s", e,
            extra={"model": model, "action": "rerank"},
        )
        raise LLMError(f"Reranking failed: {e}", provider="ollama", retriable=True)


# ============================================================
# Funções de Conveniência
# ============================================================


def extract_yaml(
    prompt: str,
    *,
    model: str | None = None,
    images: Sequence[Union[Path, str, bytes, PILImage]] | None = None,
) -> str:
    """
    Extrai YAML estruturado de um prompt.

    Wrapper que escolhe automaticamente entre texto e visão
    baseado na presença de imagens.

    Args:
        prompt: Prompt solicitando YAML
        model: Modelo a usar
        images: Imagens opcionais

    Returns:
        String YAML extraída
    """
    if images:
        model = model or DEFAULT_MODELS["vision"]
        response = generate_vision(prompt, images, model=model)
    else:
        model = model or DEFAULT_MODELS["text"]
        response = generate_text(prompt, model=model)

    content = response.content

    # Extrair bloco YAML se presente
    if "```yaml" in content:
        start = content.find("```yaml") + 7
        end = content.find("```", start)
        if end > start:
            return content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        if end > start:
            return content[start:end].strip()

    return content.strip()


def test_connection() -> dict:
    """
    Testa conexão com Ollama e retorna status.

    Returns:
        Dict com status de conexão e modelos disponíveis
    """
    result: dict[str, Any] = {
        "available": False,
        "models": [],
        "default_models": DEFAULT_MODELS,
        "missing_models": [],
    }

    if not is_ollama_available():
        return result

    result["available"] = True
    models = list_models()
    result["models"] = [m.name for m in models]

    # Verificar modelos padrão
    for task, model in DEFAULT_MODELS.items():
        if not check_model_available(model):
            result["missing_models"].append(f"{task}: {model}")

    return result


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    import json

    print("=== Ollama Adapter Test ===\n")

    status = test_connection()
    print(f"Disponível: {status['available']}")
    print(f"Modelos: {len(status['models'])}")

    if status["missing_models"]:
        print(f"\nModelos faltando:")
        for m in status["missing_models"]:
            print(f"  - {m}")

    if status["available"] and status["models"]:
        print(f"\nTestando geração de texto...")
        try:
            resp = generate_text("Responda apenas: OK", max_tokens=10)
            print(f"  Resposta: {resp.content[:50]}")
            print(f"  Tokens: {resp.total_tokens}")
            print(f"  Tempo: {resp.eval_duration_ms:.0f}ms")
        except Exception as e:
            print(f"  Erro: {e}")
