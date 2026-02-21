"""Utilidades compartilhadas para o cliente LLM."""

from __future__ import annotations

import re
from datetime import datetime
import logging

def _load_paths():
    try:
        from .config import paths as cfg_paths
    except ImportError:  # pragma: no cover - standalone usage
        from config import paths as cfg_paths
    return cfg_paths


paths = _load_paths()


def _apply_deterministic_postprocess(yaml_content: str) -> str:
    """Aplica correções determinísticas ao YAML (Complexidade, Maturidade, etc.).

    Observação: o módulo postprocess imprime logs no stdout. Para não poluir o notebook,
    suprimimos essa saída aqui.
    """
    import io
    from contextlib import redirect_stdout

    import importlib

    try:
        postprocess_mod = importlib.import_module(".postprocess", package=__package__)
    except (ImportError, ModuleNotFoundError, TypeError):
        try:
            postprocess_mod = importlib.import_module("postprocess")
        except (ImportError, ModuleNotFoundError, TypeError):
            return yaml_content

    fn = postprocess_mod.postprocess_yaml

    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            return fn(yaml_content)
    except Exception:
        return yaml_content


def extract_yaml_from_response(response: str) -> str:
    """Extrai um ÚNICO documento YAML de uma resposta do LLM.

    Handles:
    - YAML em code block (```yaml ... ```)
    - YAML puro começando com ---
    - YAML sem delimitadores

    Observação: alguns modelos retornam múltiplos documentos ("---" repetido).
    Aqui nós SEMPRE retornamos apenas o primeiro documento.
    """
    response = (response or "").strip()

    def _first_yaml_doc(text: str) -> str:
        text = (text or "").strip()
        if not text:
            return text

        # Remover qualquer texto antes do YAML (economia de tokens + evita parse ruim)
        # Preferir âncora '---' e depois 'ArtigoID'.
        if not text.startswith("---") and "---" in text:
            text = text[text.find("---"):].strip()
        elif not text.startswith("ArtigoID") and "ArtigoID" in text and "---" not in text:
            text = text[text.find("ArtigoID"):].strip()

        # Caso: começa com --- (padrão)
        if text.startswith("---"):
            # pega do primeiro --- até o próximo \n--- (fim do doc) se existir
            # mantém delimitadores externos
            rest = text[3:]
            if "\n---" in rest:
                first = rest.split("\n---", 1)[0].strip()
                return "---\n" + first + "\n---"
            # sem delimitador final: normaliza
            return "---\n" + rest.strip() + "\n---"

        # Caso: YAML sem --- mas começa com chave
        if text.startswith("ArtigoID"):
            return "---\n" + text + "\n---"

        # fallback: devolve como veio
        return text

    # Preferir bloco ```yaml ...```
    if "```yaml" in response:
        match = re.search(r"```yaml\s*\n(.*?)\n```", response, re.DOTALL)
        if match:
            yaml_result = _first_yaml_doc(match.group(1))
            return _apply_deterministic_postprocess(yaml_result)

    # Bloco ``` ... ``` genérico
    if "```" in response:
        match = re.search(r"```\s*\n(.*?)\n```", response, re.DOTALL)
        if match:
            content = match.group(1)
            if content.lstrip().startswith("---") or content.lstrip().startswith("ArtigoID"):
                yaml_result = _first_yaml_doc(content)
                return _apply_deterministic_postprocess(yaml_result)

    # Fora de code block
    yaml_result = _first_yaml_doc(response)
    return _apply_deterministic_postprocess(yaml_result)


def log_llm_call(
    artigo_id: str,
    provider: str,
    action: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    success: bool = True,
    error: str = "",
) -> None:
    """Registra chamada de LLM no log central."""
    logger = logging.getLogger("saec")
    status = "OK" if success else "ERRO"

    msg = f"{status}"
    if tokens_in or tokens_out:
        msg += f" | tokens: {tokens_in}/{tokens_out}"
    if error:
        msg += f" | {error}"

    logger.info(
        msg,
        extra={
            "artigo_id": artigo_id,
            "provider": provider,
            "action": action,
        },
    )


def log_llm_usage(
    artigo_id: str,
    provider: str,
    action: str,
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cached_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> None:
    """Registra métricas de uso/cache (linha separada para auditoria)."""
    logger = logging.getLogger("saec")
    msg = f"USAGE | tokens: {tokens_in}/{tokens_out}"
    if cached_tokens:
        msg += f" | cached_tokens: {cached_tokens}"
    if cache_read_input_tokens:
        msg += f" | cache_read_input_tokens: {cache_read_input_tokens}"
    if cache_creation_input_tokens:
        msg += f" | cache_creation_input_tokens: {cache_creation_input_tokens}"

    logger.info(
        msg,
        extra={
            "artigo_id": artigo_id,
            "provider": provider,
            "action": f"{action}_usage",
        },
    )
