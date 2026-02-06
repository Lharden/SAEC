"""Cliente unificado para LLMs (Anthropic e OpenAI)."""

from __future__ import annotations

import logging
import re
import time

# APIs
from anthropic import Anthropic
from openai import OpenAI

# Config local
try:
    from .config import llm_config, paths
    from .context import AppContext
    from .llm_client_postprocess import LLMClientPostprocessMixin
    from .llm_client_quotes import LLMClientQuotesMixin
    from .llm_client_types import LLMError, Provider, retry_with_backoff
    from .llm_utils import extract_yaml_from_response, log_llm_call, log_llm_usage
except ImportError:
    from config import llm_config, paths
    from context import AppContext
    from llm_client_postprocess import LLMClientPostprocessMixin
    from llm_client_quotes import LLMClientQuotesMixin
    from llm_client_types import LLMError, Provider, retry_with_backoff
    from llm_utils import extract_yaml_from_response, log_llm_call, log_llm_usage

# Configurar logger
logger = logging.getLogger(__name__)


class LLMClient(LLMClientPostprocessMixin, LLMClientQuotesMixin):
    """Cliente unificado para chamadas de LLM com visão.

    Nota: também suporta um provider local via Ollama (OpenAI-compatible API).

    Estratégia recomendada (custo/qualidade):
    - Extração primária via Ollama (modelo multimodal, ex: qwen3-vl:30b)
    - Validar com regras do Guia (schema + regras)
    - Repair (preferencialmente via Ollama, depois fallback)
    - Se ainda falhar, fallback para Anthropic (Claude) apenas quando necessário
    """

    def __init__(self, context: AppContext | None = None) -> None:
        """Inicializa clientes das APIs."""
        self.context = context
        self.llm_config = context.llm_config if context else llm_config
        self.paths = context.paths if context else paths

        self.anthropic = None
        self.openai = None
        self.ollama = None
        self._usage_totals = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cached_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

        timeout = self.llm_config.get_httpx_timeout()

        if self.llm_config.ANTHROPIC_API_KEY and not self.llm_config.ANTHROPIC_API_KEY.startswith("sk-ant-sua"):
            self.anthropic = Anthropic(api_key=self.llm_config.ANTHROPIC_API_KEY, timeout=timeout)

        if self.llm_config.OPENAI_API_KEY and not self.llm_config.OPENAI_API_KEY.startswith("sk-sua"):
            self.openai = OpenAI(api_key=self.llm_config.OPENAI_API_KEY, timeout=timeout)

        # Ollama (local) via OpenAI-compatible API
        if getattr(self.llm_config, "OLLAMA_ENABLED", False):
            base_url = getattr(self.llm_config, "OLLAMA_BASE_URL", "http://localhost:11434/v1")
            # Ollama ignora api_key, mas o cliente OpenAI exige um valor
            self.ollama = OpenAI(base_url=base_url, api_key="ollama", timeout=timeout)

    def _call_with_retry(self, fn, provider: str, action: str, artigo_id: str | None = None) -> str:
        wrapped = retry_with_backoff(
            max_retries=self.llm_config.RETRY_MAX_RETRIES,
            base_delay=self.llm_config.RETRY_BASE_DELAY,
            max_delay=self.llm_config.RETRY_MAX_DELAY,
            jitter=self.llm_config.RETRY_JITTER,
            max_elapsed=self.llm_config.RETRY_MAX_ELAPSED,
        )(fn)
        try:
            result = wrapped()
            log_llm_call(
                artigo_id=artigo_id or "-",
                provider=provider,
                action=action,
                success=True,
            )
            return result
        except Exception as e:
            log_llm_call(
                artigo_id=artigo_id or "-",
                provider=provider,
                action=action,
                success=False,
                error=str(e),
            )
            raise

    def reset_usage(self) -> None:
        self._usage_totals = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cached_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

    def get_usage_totals(self) -> dict:
        return dict(self._usage_totals)

    def _accumulate_usage(
        self,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cached_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
    ) -> None:
        self._usage_totals["tokens_in"] += int(tokens_in or 0)
        self._usage_totals["tokens_out"] += int(tokens_out or 0)
        self._usage_totals["cached_tokens"] += int(cached_tokens or 0)
        self._usage_totals["cache_read_input_tokens"] += int(cache_read_input_tokens or 0)
        self._usage_totals["cache_creation_input_tokens"] += int(cache_creation_input_tokens or 0)

    def _build_system_prompt(self, prompt: str, provider: str):
        if provider == "anthropic":
            if self.llm_config.PROMPT_CACHE_ENABLED:
                return [
                    {
                        "type": "text",
                        "text": prompt,
                        "cache_control": {
                            "type": "ephemeral",
                            "ttl": self.llm_config.ANTHROPIC_CACHE_TTL,
                        },
                    }
                ]
            return prompt
        # OpenAI/Ollama: usar system role (cache automático por prefixo)
        return prompt

    def _check_provider(self, provider: Provider) -> None:
        """Verifica se o provider está disponível."""
        if provider == "anthropic" and not self.anthropic:
            raise ValueError("Anthropic API não configurada. Verifique ANTHROPIC_API_KEY no .env")
        if provider == "openai" and not self.openai:
            raise ValueError("OpenAI API não configurada. Verifique OPENAI_API_KEY no .env")
        if provider == "ollama" and not self.ollama:
            raise ValueError(
                "Ollama não configurado/indisponível. Verifique se o serviço está rodando e OLLAMA_ENABLED/OLLAMA_BASE_URL no .env"
            )

    def extract_with_vision(
        self,
        images: list[dict],
        prompt: str,
        artigo_id: str,
        provider: Provider = "anthropic",
        max_tokens: int = 8000
    ) -> str:
        """
        Extrai dados do artigo usando LLM com visão.

        Args:
            images: Lista de imagens no formato do provider
            prompt: Prompt do Guia v3.3
            artigo_id: ID do artigo (ART_001, etc.)
            provider: "anthropic" ou "openai"
            max_tokens: Limite de tokens na resposta

        Returns:
            Resposta do LLM (texto com YAML)
        """
        self._check_provider(provider)

        system_prompt = self._build_system_prompt(prompt, provider)

        user_message = f"""ArtigoID: {artigo_id}

Analise as páginas do artigo acima e extraia os dados CIMO.

IMPORTANTE:
1. Retorne SOMENTE o YAML, sem explicações antes ou depois
2. Use o formato EXATO do template
3. Todas as quotes devem ser LITERAIS (cópia exata do texto)
4. Mecanismo_Estruturado deve ser STRING ÚNICA (sem quebras de linha)
5. Cada sentença de Mecanismo_Inferido deve começar com "INFERIDO:"

Comece o YAML com --- e termine com ---"""

        # Ollama (OpenAI-compatible) pode suportar visão quando usado com um modelo multimodal
        # (ex: qwen3-vl:*). Mantemos o provider explícito para controle e fallback.
        if provider == "anthropic":
            return self._call_anthropic_vision(images, user_message, max_tokens, artigo_id=artigo_id, system_prompt=system_prompt)
        if provider == "openai":
            return self._call_openai_vision(images, user_message, max_tokens, artigo_id=artigo_id, system_prompt=system_prompt)
        # provider == "ollama"
        return self._call_ollama_vision(images, user_message, max_tokens, artigo_id=artigo_id, system_prompt=system_prompt)

    def extract_with_hybrid(
        self,
        content: list[dict],
        prompt: str,
        artigo_id: str,
        provider: Provider = "anthropic",
        max_tokens: int = 8000
    ) -> str:
        """
        Extrai dados do artigo usando conteúdo híbrido (texto + imagens).

        Args:
            content: Lista de content blocks (texto e imagens misturados)
            prompt: Prompt do Guia v3.3
            artigo_id: ID do artigo (ART_001, etc.)
            provider: "anthropic" ou "openai"
            max_tokens: Limite de tokens na resposta

        Returns:
            Resposta do LLM (texto com YAML)
        """
        self._check_provider(provider)

        system_prompt = self._build_system_prompt(prompt, provider)

        intro = f"""ArtigoID: {artigo_id}

Abaixo está o conteúdo do artigo. Páginas com figuras/tabelas são enviadas como imagens.
Páginas apenas com texto são enviadas como texto extraído.
As páginas de referências bibliográficas foram omitidas.

Analise todo o conteúdo e extraia os dados CIMO.

IMPORTANTE:
1. Retorne SOMENTE o YAML, sem explicações antes ou depois
2. Use o formato EXATO do template
3. Todas as quotes devem ser LITERAIS (cópia exata do texto)
4. Mecanismo_Estruturado deve ser STRING ÚNICA (sem quebras de linha)
5. Cada sentença de Mecanismo_Inferido deve começar com "INFERIDO:"

Comece o YAML com --- e termine com ---

=== CONTEÚDO DO ARTIGO ===
"""

        if provider == "anthropic":
            return self._call_anthropic_hybrid(content, intro, max_tokens, artigo_id=artigo_id, system_prompt=system_prompt)
        if provider == "openai":
            return self._call_openai_hybrid(content, intro, max_tokens, artigo_id=artigo_id, system_prompt=system_prompt)
        # provider == "ollama" (OpenAI-compatible)
        return self._call_ollama_hybrid(content, intro, max_tokens, artigo_id=artigo_id, system_prompt=system_prompt)

    def _call_anthropic_hybrid(
        self,
        content: list[dict],
        intro: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: object | None = None,
    ) -> str:
        """Chamada para Claude com conteúdo híbrido."""
        def _do_call() -> str:
            message_content = [{"type": "text", "text": intro}]
            message_content.extend(content)
            response = self.anthropic.messages.create(
                model=self.llm_config.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": message_content}],
            )
            usage = getattr(response, "usage", None)
            if usage:
                log_llm_usage(
                    artigo_id or "-",
                    "anthropic",
                    "extract_hybrid",
                    tokens_in=getattr(usage, "input_tokens", 0),
                    tokens_out=getattr(usage, "output_tokens", 0),
                    cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0),
                    cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0),
                )
                self._accumulate_usage(
                    tokens_in=getattr(usage, "input_tokens", 0),
                    tokens_out=getattr(usage, "output_tokens", 0),
                    cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0),
                    cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0),
                )
            return response.content[0].text

        try:
            return self._call_with_retry(_do_call, provider="anthropic", action="extract_hybrid", artigo_id=artigo_id)
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise LLMError(str(e), provider="anthropic", retriable=True)

    def _call_openai_hybrid(
        self,
        content: list[dict],
        intro: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: object | None = None,
    ) -> str:
        """Chamada para OpenAI com conteúdo híbrido."""
        def _do_call() -> str:
            message_content = [{"type": "text", "text": intro}]
            message_content.extend(content)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message_content})
            response = self.openai.chat.completions.create(
                model=self.llm_config.OPENAI_MODEL,
                max_completion_tokens=max_tokens,
                messages=messages,
                prompt_cache_key=self.llm_config.PROMPT_CACHE_KEY if self.llm_config.PROMPT_CACHE_ENABLED else None,
                prompt_cache_retention=self.llm_config.PROMPT_CACHE_RETENTION if self.llm_config.PROMPT_CACHE_ENABLED else None,
            )
            usage = getattr(response, "usage", None)
            if usage:
                details = getattr(usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details else 0
                log_llm_usage(
                    artigo_id or "-",
                    "openai",
                    "extract_hybrid",
                    tokens_in=getattr(usage, "prompt_tokens", 0),
                    tokens_out=getattr(usage, "completion_tokens", 0),
                    cached_tokens=cached,
                )
                self._accumulate_usage(
                    tokens_in=getattr(usage, "prompt_tokens", 0),
                    tokens_out=getattr(usage, "completion_tokens", 0),
                    cached_tokens=cached,
                )
            return response.choices[0].message.content

        try:
            return self._call_with_retry(_do_call, provider="openai", action="extract_hybrid", artigo_id=artigo_id)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMError(str(e), provider="openai", retriable=True)

    def _call_ollama_hybrid(
        self,
        content: list[dict],
        intro: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: object | None = None,
    ) -> str:
        """Chamada para Ollama (OpenAI-compatible) com conteúdo híbrido."""
        def _do_call() -> str:
            message_content = [{"type": "text", "text": intro}]
            message_content.extend(content)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message_content})
            model = self.llm_config.OLLAMA_MODEL_VISION
            response = self.ollama.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content

        try:
            return self._call_with_retry(_do_call, provider="ollama", action="extract_hybrid", artigo_id=artigo_id)
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise LLMError(str(e), provider="ollama", retriable=True)

    def _call_anthropic_vision(
        self,
        images: list[dict],
        user_message: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: object | None = None,
    ) -> str:
        """Chamada para Claude com visão."""
        def _do_call() -> str:
            content = []
            for img in images:
                content.append(img)
            content.append({"type": "text", "text": user_message})
            response = self.anthropic.messages.create(
                model=self.llm_config.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": content}],
            )
            usage = getattr(response, "usage", None)
            if usage:
                log_llm_usage(
                    artigo_id or "-",
                    "anthropic",
                    "extract_vision",
                    tokens_in=getattr(usage, "input_tokens", 0),
                    tokens_out=getattr(usage, "output_tokens", 0),
                    cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0),
                    cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0),
                )
                self._accumulate_usage(
                    tokens_in=getattr(usage, "input_tokens", 0),
                    tokens_out=getattr(usage, "output_tokens", 0),
                    cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0),
                    cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0),
                )
            return response.content[0].text

        try:
            return self._call_with_retry(_do_call, provider="anthropic", action="extract_vision", artigo_id=artigo_id)
        except Exception as e:
            logger.error(f"Anthropic Vision API error: {e}")
            raise LLMError(str(e), provider="anthropic", retriable=True)

    def _call_openai_vision(
        self,
        images: list[dict],
        user_message: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: object | None = None,
    ) -> str:
        """Chamada para OpenAI com visão."""
        def _do_call() -> str:
            content = list(images)
            content.append({"type": "text", "text": user_message})
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": content})
            response = self.openai.chat.completions.create(
                model=self.llm_config.OPENAI_MODEL,
                max_completion_tokens=max_tokens,
                messages=messages,
                prompt_cache_key=self.llm_config.PROMPT_CACHE_KEY if self.llm_config.PROMPT_CACHE_ENABLED else None,
                prompt_cache_retention=self.llm_config.PROMPT_CACHE_RETENTION if self.llm_config.PROMPT_CACHE_ENABLED else None,
            )
            usage = getattr(response, "usage", None)
            if usage:
                details = getattr(usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details else 0
                log_llm_usage(
                    artigo_id or "-",
                    "openai",
                    "extract_vision",
                    tokens_in=getattr(usage, "prompt_tokens", 0),
                    tokens_out=getattr(usage, "completion_tokens", 0),
                    cached_tokens=cached,
                )
                self._accumulate_usage(
                    tokens_in=getattr(usage, "prompt_tokens", 0),
                    tokens_out=getattr(usage, "completion_tokens", 0),
                    cached_tokens=cached,
                )
            return response.choices[0].message.content

        try:
            return self._call_with_retry(_do_call, provider="openai", action="extract_vision", artigo_id=artigo_id)
        except Exception as e:
            logger.error(f"OpenAI Vision API error: {e}")
            raise LLMError(str(e), provider="openai", retriable=True)

    def _call_ollama_vision(
        self,
        images: list[dict],
        user_message: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: object | None = None,
    ) -> str:
        """Chamada para Ollama (OpenAI-compatible) com visão."""
        def _do_call() -> str:
            content = list(images)
            content.append({"type": "text", "text": user_message})
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": content})
            model = self.llm_config.OLLAMA_MODEL_VISION
            response = self.ollama.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content

        try:
            return self._call_with_retry(_do_call, provider="ollama", action="extract_vision", artigo_id=artigo_id)
        except Exception as e:
            logger.error(f"Ollama Vision API error: {e}")
            raise LLMError(str(e), provider="ollama", retriable=True)

    def repair_yaml(
        self,
        yaml_content: str,
        errors: list[str],
        provider: Provider = "ollama",  # Prioriza modelo local para economia
        max_tokens: int = 8000
    ) -> str:
        """
        Repara YAML com erros de validação.

        Args:
            yaml_content: YAML com erros
            errors: Lista de erros encontrados
            provider: LLM para usar (default: openai para repairs)
            max_tokens: Limite de tokens

        Returns:
            YAML corrigido
        """
        # Roteamento automático: preferir Ollama (local) para repairs.
        # Se Ollama indisponível, fallback para OpenAI/Anthropic.
        if provider == "ollama" and not self.ollama:
            if self.openai:
                provider = "openai"
                logger.warning("Ollama indisponivel, usando OpenAI para repair")
            elif self.anthropic:
                provider = "anthropic"
                logger.warning("Ollama indisponivel, usando Anthropic para repair")
        elif provider == "openai" and not self.openai:
            if self.ollama:
                provider = "ollama"
            elif self.anthropic:
                provider = "anthropic"
        elif provider == "anthropic" and not self.anthropic:
            if self.ollama:
                provider = "ollama"
            elif self.openai:
                provider = "openai"

        self._check_provider(provider)

        repair_prompt = f"""Corrija APENAS os erros listados abaixo. Retorne SOMENTE YAML valido.

ERROS:
{chr(10).join(f"- {e}" for e in errors)}

YAML:
```yaml
{yaml_content}
```

REGRAS:
1. Corrija somente campos citados nos erros.
2. Preserve todo o resto exatamente como esta.
3. Nao altere textos de quotes ou narrativas.
4. YAML deve ser parseavel (PyYAML). Quotes.Trecho com ':' devem estar entre aspas.
5. Comece com --- e termine com ---.
6. Mecanismo_Estruturado: uma unica linha "Entrada → Transformacao → Mediacao → Resultado".
7. Mecanismo_Inferido: cada sentenca comeca com "INFERIDO:".
8. Complexidade_Justificativa deve conter F1=, F2=, F3=.
9. QuoteID: Q001, Q002, Q003...

YAML corrigido:"""

        def _call_openai_client(client: OpenAI, model: str) -> str:
            response = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um assistente especializado em corrigir YAML. Retorne APENAS YAML válido, sem explicações.",
                    },
                    {"role": "user", "content": repair_prompt},
                ],
            )
            return response.choices[0].message.content

        # Estratégia: preferir Ollama (Qwen) para tarefas mecânicas (repair).
        # Se falhar, cair para OpenAI; por fim, Anthropic.
        if provider == "ollama":
            try:
                # Para repairs (mecânico), usar modelo coder dedicado
                model = self.llm_config.OLLAMA_MODEL_CODER
                return _call_openai_client(self.ollama, model)
            except Exception as e:
                # Fallback automático
                if self.openai:
                    try:
                        return _call_openai_client(self.openai, self.llm_config.OPENAI_MODEL)
                    except Exception:
                        pass
                if self.anthropic:
                    response = self.anthropic.messages.create(
                        model=self.llm_config.ANTHROPIC_MODEL,
                        max_tokens=max_tokens,
                        messages=[{"role": "user", "content": repair_prompt}]
                    )
                    return response.content[0].text
                raise e

        if provider == "openai":
            return _call_openai_client(self.openai, self.llm_config.OPENAI_MODEL)

        # provider == anthropic
        response = self.anthropic.messages.create(
            model=self.llm_config.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": repair_prompt}
            ]
        )
        return response.content[0].text

if __name__ == "__main__":
    print("=== LLM Client Test ===")

    client = LLMClient()

    print("\nStatus dos providers:")
    print(f"  Anthropic: {'CONFIGURADO' if client.anthropic else 'NAO CONFIGURADO'}")
    print(f"  OpenAI: {'CONFIGURADO' if client.openai else 'NAO CONFIGURADO'}")
    print(f"  Ollama: {'CONFIGURADO' if client.ollama else 'NAO CONFIGURADO'}")

    print("\nModelos configurados:")
    print(f"  Anthropic: {llm_config.ANTHROPIC_MODEL}")
    print(f"  OpenAI: {llm_config.OPENAI_MODEL}")
    if getattr(llm_config, 'OLLAMA_ENABLED', False):
        print(f"  Ollama coder: {llm_config.OLLAMA_MODEL_CODER}")
        print(f"  Ollama vision: {llm_config.OLLAMA_MODEL_VISION}")

    print("\nEstrategia:")
    print(f"  Two-pass: {llm_config.USE_TWO_PASS}")
    print(f"  Primary: {llm_config.PRIMARY_PROVIDER}")
