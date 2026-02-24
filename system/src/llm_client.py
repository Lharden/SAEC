"""Cliente unificado para LLMs com registro dinâmico de provedores."""

from __future__ import annotations

import logging
from typing import Any, Union, cast

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

# ---------------------------------------------------------------------------
# Specific exception types for LLM provider API calls
# ---------------------------------------------------------------------------
_LLM_API_ERRORS: tuple[type[Exception], ...] = (ConnectionError, TimeoutError, OSError)
try:
    import httpx

    _LLM_API_ERRORS = (*_LLM_API_ERRORS, httpx.HTTPError, httpx.TimeoutException)
except (ImportError, ModuleNotFoundError):
    pass
try:
    from anthropic import APIError as _AnthropicAPIError, APIConnectionError as _AnthropicConnError

    _LLM_API_ERRORS = (*_LLM_API_ERRORS, _AnthropicAPIError, _AnthropicConnError)
except (ImportError, ModuleNotFoundError):
    pass
try:
    from openai import OpenAIError as _OpenAIError

    _LLM_API_ERRORS = (*_LLM_API_ERRORS, _OpenAIError)
except (ImportError, ModuleNotFoundError):
    pass


class LLMClient(LLMClientPostprocessMixin, LLMClientQuotesMixin):
    """Cliente unificado para chamadas de LLM com visão.

    Nota: também suporta um provider local via Ollama (OpenAI-compatible API).

    Estratégia recomendada (custo/qualidade):
    - Extração textual via Ollama cloud proxy
    - Extração com imagens via modelo vision local
    - Repair com cadeia cloud -> cloud_fallback -> OpenAI -> Anthropic
    """

    def __init__(self, context: AppContext | None = None) -> None:
        """Inicializa clientes das APIs."""
        self.context = context
        self.llm_config = context.llm_config if context else llm_config
        self.paths = context.paths if context else paths

        self.anthropic: Anthropic | None = None
        self.openai: OpenAI | None = None
        self.ollama: OpenAI | None = None
        if hasattr(self.llm_config, "get_provider_registry"):
            self._provider_specs: dict[str, dict[str, str]] = (
                self.llm_config.get_provider_registry()
            )
        else:
            self._provider_specs = self._legacy_specs_from_config()
        self._openai_like_clients: dict[str, OpenAI] = {}
        self._anthropic_clients: dict[str, Anthropic] = {}
        self._usage_totals = {
            "tokens_in": 0,
            "tokens_out": 0,
            "cached_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

        timeout = self.llm_config.get_httpx_timeout()
        self._build_provider_clients(timeout=timeout)

    def _legacy_specs_from_config(self) -> dict[str, dict[str, str]]:
        return {
            "anthropic": {
                "kind": "anthropic",
                "enabled": "true",
                "api_key": str(getattr(self.llm_config, "ANTHROPIC_API_KEY", "") or "").strip(),
                "api_key_env": "",
                "base_url": "",
                "model": str(getattr(self.llm_config, "ANTHROPIC_MODEL", "") or "").strip(),
                "vision_model": "",
                "repair_model": "",
            },
            "openai": {
                "kind": "openai_compatible",
                "enabled": "true",
                "api_key": str(getattr(self.llm_config, "OPENAI_API_KEY", "") or "").strip(),
                "api_key_env": "",
                "base_url": str(getattr(self.llm_config, "OPENAI_BASE_URL", "") or "").strip(),
                "model": str(getattr(self.llm_config, "OPENAI_MODEL", "") or "").strip(),
                "vision_model": "",
                "repair_model": "",
            },
            "ollama": {
                "kind": "ollama",
                "enabled": "true"
                if bool(getattr(self.llm_config, "OLLAMA_ENABLED", False))
                else "false",
                "api_key": "ollama",
                "api_key_env": "",
                "base_url": str(getattr(self.llm_config, "OLLAMA_BASE_URL", "") or "").strip(),
                "model": str(getattr(self.llm_config, "OLLAMA_MODEL_CLOUD", "") or "").strip(),
                "vision_model": str(
                    getattr(self.llm_config, "OLLAMA_MODEL_VISION", "") or ""
                ).strip(),
                "repair_model": str(
                    getattr(self.llm_config, "OLLAMA_MODEL_CLOUD_FALLBACK", "") or ""
                ).strip(),
            },
        }

    def _build_provider_clients(self, *, timeout: Any) -> None:
        for provider_id, spec in self._provider_specs.items():
            kind = (spec.get("kind", "openai_compatible") or "openai_compatible").strip().lower()
            if not self._spec_enabled(spec):
                continue

            if kind == "anthropic":
                api_key = self._spec_api_key(spec)
                if not api_key:
                    continue
                client = Anthropic(api_key=api_key, timeout=timeout)
                self._anthropic_clients[provider_id] = client
                if provider_id == "anthropic":
                    self.anthropic = client
                continue

            api_key = self._spec_api_key(spec)
            if kind != "ollama" and not api_key:
                continue
            base_url = (spec.get("base_url", "") or "").strip()
            kwargs: dict[str, Any] = {"api_key": api_key or "ollama", "timeout": timeout}
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
            self._openai_like_clients[provider_id] = client
            if provider_id == "openai":
                self.openai = client
            if provider_id == "ollama":
                self.ollama = client

    @staticmethod
    def _spec_enabled(spec: dict[str, str]) -> bool:
        return str(spec.get("enabled", "true")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    @staticmethod
    def _spec_api_key(spec: dict[str, str]) -> str:
        literal = (spec.get("api_key", "") or "").strip()
        if literal:
            return literal
        env_key = (spec.get("api_key_env", "") or "").strip()
        if env_key:
            import os

            return os.getenv(env_key, "").strip()
        return ""

    def get_provider_kind(self, provider: str) -> str:
        normalized = (provider or "").strip().lower()
        spec = self._provider_specs.get(normalized)
        if not spec:
            if normalized == "anthropic":
                return "anthropic"
            if normalized == "ollama":
                return "ollama"
            return "openai_compatible"
        return (spec.get("kind", "openai_compatible") or "openai_compatible").strip().lower()

    def get_provider_model(self, provider: str, purpose: str = "default") -> str:
        normalized = (provider or "").strip().lower()
        # Compatibilidade legado: respeitar llm_config atual para providers padrão.
        if normalized == "anthropic":
            return getattr(self.llm_config, "ANTHROPIC_MODEL", "")
        if normalized == "openai":
            return getattr(self.llm_config, "OPENAI_MODEL", "")
        if normalized == "ollama":
            if purpose == "vision":
                return getattr(self.llm_config, "OLLAMA_MODEL_VISION", "")
            if purpose == "repair":
                return getattr(self.llm_config, "OLLAMA_MODEL_CLOUD_FALLBACK", "")
            return getattr(self.llm_config, "OLLAMA_MODEL_CLOUD", "")

        spec = self._provider_specs.get(normalized, {})
        if purpose == "vision":
            model = (spec.get("vision_model", "") or "").strip()
            if model:
                return model
        if purpose == "repair":
            model = (spec.get("repair_model", "") or "").strip()
            if model:
                return model

        model = (spec.get("model", "") or "").strip()
        if model:
            return model

        # fallback legado para providers não-cadastrados
        return getattr(self.llm_config, "OPENAI_MODEL", "")

    def get_openai_client(self, provider: str) -> OpenAI:
        normalized = (provider or "").strip().lower()
        if self.openai and normalized == "openai":
            return self.openai
        if self.ollama and normalized == "ollama":
            return self.ollama
        client = self._openai_like_clients.get(normalized)
        if client:
            return client
        raise ValueError(f"Provider OpenAI-compatible indisponível: {provider}")

    def get_anthropic_client(self, provider: str) -> Anthropic:
        normalized = (provider or "").strip().lower()
        if self.anthropic and normalized == "anthropic":
            return self.anthropic
        client = self._anthropic_clients.get(normalized)
        if client:
            return client
        raise ValueError(f"Provider Anthropic indisponível: {provider}")

    def list_available_providers(self) -> dict[str, bool]:
        status: dict[str, bool] = {
            "anthropic": self.anthropic is not None,
            "openai": self.openai is not None,
            "ollama": self.ollama is not None,
        }
        for provider_id in self._provider_specs.keys():
            kind = self.get_provider_kind(provider_id)
            if kind == "anthropic":
                status[provider_id] = provider_id in self._anthropic_clients
            else:
                status[provider_id] = provider_id in self._openai_like_clients
        return status

    def _call_with_retry(self, fn, provider: str, action: str, artigo_id: str | None = None) -> str:
        """Execute LLM call with exponential backoff, jitter, and configurable max retries."""
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
        except Exception as e:  # Intentional: catch-all for retry/fallback logic
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

    def _build_system_prompt(self, prompt: str, provider: str) -> Union[str, list[dict[str, Any]]]:
        if self.get_provider_kind(provider) == "anthropic":
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

    def _create_openai_chat_completion(
        self,
        *,
        client: OpenAI,
        model: str,
        max_tokens: int,
        messages: list[dict],
        use_prompt_cache: bool,
        provider_label: str,
    ):
        kwargs = {
            "model": model,
            "max_completion_tokens": max_tokens,
            "messages": messages,
        }
        if use_prompt_cache:
            kwargs["prompt_cache_key"] = self.llm_config.PROMPT_CACHE_KEY
            kwargs["prompt_cache_retention"] = self.llm_config.PROMPT_CACHE_RETENTION

        try:
            return client.chat.completions.create(**kwargs)
        except TypeError as exc:
            # Compatibilidade com SDKs que ainda não suportam prompt cache kwargs.
            err_text = str(exc)
            unsupported = "prompt_cache_key" in err_text or "prompt_cache_retention" in err_text
            if unsupported and use_prompt_cache:
                logger.warning(
                    "OpenAI SDK sem suporte a prompt cache kwargs; repetindo chamada sem cache",
                    extra={"provider": provider_label, "action": "extract"},
                )
                kwargs.pop("prompt_cache_key", None)
                kwargs.pop("prompt_cache_retention", None)
                return client.chat.completions.create(**kwargs)
            raise

    def _check_provider(self, provider: Provider) -> None:
        """Verifica se o provider está disponível."""
        normalized = (provider or "").strip().lower()
        kind = self.get_provider_kind(normalized)
        if kind == "anthropic":
            if normalized in self._anthropic_clients:
                return
            if normalized == "anthropic" and self.anthropic is not None:
                return
            raise ValueError(f"Provider '{provider}' (anthropic) não configurado ou indisponível")
        if normalized in self._openai_like_clients:
            return
        if normalized == "openai" and self.openai is not None:
            return
        if normalized == "ollama" and self.ollama is not None:
            return
        raise ValueError(
            f"Provider '{provider}' (openai-compatible/ollama) não configurado ou indisponível"
        )

    @staticmethod
    def _has_image_blocks(content: list[dict]) -> bool:
        return any(
            isinstance(block, dict) and block.get("type") == "image_url" for block in content
        )

    def _get_ollama_hybrid_model(self, content: list[dict]) -> str:
        return (
            self.llm_config.OLLAMA_MODEL_VISION
            if self._has_image_blocks(content)
            else self.llm_config.OLLAMA_MODEL_CLOUD
        )

    def _iter_ollama_repair_models(self) -> list[str]:
        candidates = [
            getattr(self.llm_config, "OLLAMA_MODEL_CLOUD", ""),
            getattr(self.llm_config, "OLLAMA_MODEL_CLOUD_FALLBACK", ""),
        ]
        ordered_unique: list[str] = []
        for model in candidates:
            if model and model not in ordered_unique:
                ordered_unique.append(model)
        return ordered_unique

    @staticmethod
    def _extract_anthropic_text(response: Any) -> str:
        content = getattr(response, "content", None)
        if not isinstance(content, list):
            return ""
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text:
                return text
            if isinstance(block, dict):
                dict_text = block.get("text")
                if isinstance(dict_text, str) and dict_text:
                    return dict_text
        return ""

    def extract_with_vision(
        self,
        images: list[dict],
        prompt: str,
        artigo_id: str,
        provider: Provider = "anthropic",
        max_tokens: int = 8000,
    ) -> str:
        """
        Extrai dados do artigo usando LLM com visão.

        Args:
            images: Lista de imagens no formato do provider
            prompt: Prompt do Guia v3.3
            artigo_id: ID do artigo (ART_001, etc.)
            provider: "anthropic", "openai" ou "ollama"
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
        provider_kind = self.get_provider_kind(provider)
        if provider_kind == "anthropic":
            return self._call_anthropic_vision(
                images,
                user_message,
                max_tokens,
                artigo_id=artigo_id,
                system_prompt=system_prompt,
                provider=provider,
            )
        if provider_kind == "ollama":
            return self._call_ollama_vision(
                images,
                user_message,
                max_tokens,
                artigo_id=artigo_id,
                system_prompt=cast(str, system_prompt),
                provider=provider,
            )
        return self._call_openai_vision(
            images,
            user_message,
            max_tokens,
            artigo_id=artigo_id,
            system_prompt=cast(str, system_prompt),
            provider=provider,
        )

    def extract_with_hybrid(
        self,
        content: list[dict],
        prompt: str,
        artigo_id: str,
        provider: Provider = "anthropic",
        max_tokens: int = 8000,
    ) -> str:
        """
        Extrai dados do artigo usando conteúdo híbrido (texto + imagens).

        Args:
            content: Lista de content blocks (texto e imagens misturados)
            prompt: Prompt do Guia v3.3
            artigo_id: ID do artigo (ART_001, etc.)
            provider: "anthropic", "openai" ou "ollama"
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

        provider_kind = self.get_provider_kind(provider)
        if provider_kind == "anthropic":
            return self._call_anthropic_hybrid(
                content,
                intro,
                max_tokens,
                artigo_id=artigo_id,
                system_prompt=system_prompt,
                provider=provider,
            )
        if provider_kind == "ollama":
            return self._call_ollama_hybrid(
                content,
                intro,
                max_tokens,
                artigo_id=artigo_id,
                system_prompt=cast(str, system_prompt),
                provider=provider,
            )
        return self._call_openai_hybrid(
            content,
            intro,
            max_tokens,
            artigo_id=artigo_id,
            system_prompt=cast(str, system_prompt),
            provider=provider,
        )

    def _call_anthropic_hybrid(
        self,
        content: list[dict],
        intro: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: Union[str, list[dict[str, Any]]] | None = None,
        provider: str = "anthropic",
    ) -> str:
        """Chamada para Claude com conteúdo híbrido."""
        anthropic_client = self.get_anthropic_client(provider)
        model_name = self.get_provider_model(provider)

        def _do_call() -> str:
            message_content = [{"type": "text", "text": intro}]
            message_content.extend(content)
            create_message = cast(Any, anthropic_client.messages.create)
            kwargs: dict[str, Any] = {
                "model": model_name,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": message_content}],
            }
            if system_prompt is not None:
                kwargs["system"] = system_prompt
            response = create_message(
                **kwargs,
            )
            usage = getattr(response, "usage", None)
            if usage:
                log_llm_usage(
                    artigo_id or "-",
                    provider,
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
            return self._extract_anthropic_text(response)

        try:
            return self._call_with_retry(
                _do_call,
                provider=provider,
                action="extract_hybrid",
                artigo_id=artigo_id,
            )
        except _LLM_API_ERRORS as e:
            logger.error(
                "Anthropic hybrid API error: %s",
                e,
                extra={
                    "provider": "anthropic",
                    "provider_id": provider,
                    "action": "extract_hybrid",
                    "artigo_id": artigo_id or "-",
                },
            )
            raise LLMError(str(e), provider=provider, retriable=True)

    def _call_openai_hybrid(
        self,
        content: list[dict],
        intro: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: str | None = None,
        provider: str = "openai",
    ) -> str:
        """Chamada para OpenAI com conteúdo híbrido."""
        openai_client = self.get_openai_client(provider)

        def _do_call() -> str:
            message_content = [{"type": "text", "text": intro}]
            message_content.extend(content)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message_content})
            response = self._create_openai_chat_completion(
                client=openai_client,
                model=self.get_provider_model(provider),
                max_tokens=max_tokens,
                messages=messages,
                use_prompt_cache=bool(self.llm_config.PROMPT_CACHE_ENABLED),
                provider_label=provider,
            )
            usage = getattr(response, "usage", None)
            if usage:
                details = getattr(usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details else 0
                log_llm_usage(
                    artigo_id or "-",
                    provider,
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
            return response.choices[0].message.content or ""

        try:
            return self._call_with_retry(
                _do_call,
                provider=provider,
                action="extract_hybrid",
                artigo_id=artigo_id,
            )
        except _LLM_API_ERRORS as e:
            logger.error(
                "OpenAI hybrid API error: %s",
                e,
                extra={
                    "provider": "openai",
                    "provider_id": provider,
                    "action": "extract_hybrid",
                    "artigo_id": artigo_id or "-",
                },
            )
            raise LLMError(str(e), provider=provider, retriable=True)

    def _call_ollama_hybrid(
        self,
        content: list[dict],
        intro: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: str | None = None,
        provider: str = "ollama",
    ) -> str:
        """Chamada para Ollama (OpenAI-compatible) com conteúdo híbrido.

        Usa modelo cloud (glm-4.7:cloud) para extração por padrão.
        Conteúdo com imagens usa modelo vision local (qwen3-vl:8b).
        """

        def _do_call() -> str:
            message_content = [{"type": "text", "text": intro}]
            message_content.extend(content)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message_content})
            if provider == "ollama":
                model = self._get_ollama_hybrid_model(content)
            else:
                model = self.get_provider_model(
                    provider,
                    "vision" if self._has_image_blocks(content) else "default",
                )
            response = self.get_openai_client(provider).chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content or ""

        try:
            return self._call_with_retry(
                _do_call,
                provider=provider,
                action="extract_hybrid",
                artigo_id=artigo_id,
            )
        except _LLM_API_ERRORS as e:
            logger.error(
                "Ollama hybrid API error: %s",
                e,
                extra={
                    "provider": "ollama",
                    "provider_id": provider,
                    "action": "extract_hybrid",
                    "artigo_id": artigo_id or "-",
                },
            )
            raise LLMError(str(e), provider=provider, retriable=True)

    def _call_anthropic_vision(
        self,
        images: list[dict],
        user_message: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: Union[str, list[dict[str, Any]]] | None = None,
        provider: str = "anthropic",
    ) -> str:
        """Chamada para Claude com visão."""
        anthropic_client = self.get_anthropic_client(provider)

        def _do_call() -> str:
            content = []
            for img in images:
                content.append(img)
            content.append({"type": "text", "text": user_message})
            create_message = cast(Any, anthropic_client.messages.create)
            kwargs: dict[str, Any] = {
                "model": self.get_provider_model(provider, "vision"),
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": content}],
            }
            if system_prompt is not None:
                kwargs["system"] = system_prompt
            response = create_message(**kwargs)
            usage = getattr(response, "usage", None)
            if usage:
                log_llm_usage(
                    artigo_id or "-",
                    provider,
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
            return self._extract_anthropic_text(response)

        try:
            return self._call_with_retry(
                _do_call,
                provider=provider,
                action="extract_vision",
                artigo_id=artigo_id,
            )
        except _LLM_API_ERRORS as e:
            logger.error(
                "Anthropic vision API error: %s",
                e,
                extra={
                    "provider": "anthropic",
                    "provider_id": provider,
                    "action": "extract_vision",
                    "artigo_id": artigo_id or "-",
                },
            )
            raise LLMError(str(e), provider=provider, retriable=True)

    def _call_openai_vision(
        self,
        images: list[dict],
        user_message: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: str | None = None,
        provider: str = "openai",
    ) -> str:
        """Chamada para OpenAI com visão."""
        openai_client = self.get_openai_client(provider)

        def _do_call() -> str:
            content = list(images)
            content.append({"type": "text", "text": user_message})
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": content})
            response = self._create_openai_chat_completion(
                client=openai_client,
                model=self.get_provider_model(provider, "vision"),
                max_tokens=max_tokens,
                messages=messages,
                use_prompt_cache=bool(self.llm_config.PROMPT_CACHE_ENABLED),
                provider_label=provider,
            )
            usage = getattr(response, "usage", None)
            if usage:
                details = getattr(usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details else 0
                log_llm_usage(
                    artigo_id or "-",
                    provider,
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
            return response.choices[0].message.content or ""

        try:
            return self._call_with_retry(
                _do_call,
                provider=provider,
                action="extract_vision",
                artigo_id=artigo_id,
            )
        except _LLM_API_ERRORS as e:
            logger.error(
                "OpenAI vision API error: %s",
                e,
                extra={
                    "provider": "openai",
                    "provider_id": provider,
                    "action": "extract_vision",
                    "artigo_id": artigo_id or "-",
                },
            )
            raise LLMError(str(e), provider=provider, retriable=True)

    def _call_ollama_vision(
        self,
        images: list[dict],
        user_message: str,
        max_tokens: int,
        artigo_id: str | None = None,
        system_prompt: str | None = None,
        provider: str = "ollama",
    ) -> str:
        """Chamada para Ollama (OpenAI-compatible) com visão."""

        def _do_call() -> str:
            content = list(images)
            content.append({"type": "text", "text": user_message})
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": content})
            model = self.get_provider_model(provider, "vision")
            response = self.get_openai_client(provider).chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            return response.choices[0].message.content or ""

        try:
            return self._call_with_retry(
                _do_call,
                provider=provider,
                action="extract_vision",
                artigo_id=artigo_id,
            )
        except _LLM_API_ERRORS as e:
            logger.error(
                "Ollama vision API error: %s",
                e,
                extra={
                    "provider": "ollama",
                    "provider_id": provider,
                    "action": "extract_vision",
                    "artigo_id": artigo_id or "-",
                },
            )
            raise LLMError(str(e), provider=provider, retriable=True)

    def repair_yaml(
        self,
        yaml_content: str,
        errors: list[str],
        provider: Provider = "ollama",
        max_tokens: int = 8000,
    ) -> str:
        """
        Repara YAML com erros de validação.

        O caller (processors.py) resolve o provider via _resolve_provider_for_task.
        Para Ollama, tenta cadeia de modelos (cloud → cloud_fallback).
        Todas as chamadas usam retry com backoff.
        """
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

        repair_system = "Você é um assistente especializado em corrigir YAML. Retorne APENAS YAML válido, sem explicações."

        kind = self.get_provider_kind(provider)
        order = [provider]
        available = self.list_available_providers()
        for provider_id, enabled in available.items():
            if enabled and provider_id != provider:
                order.append(provider_id)

        last_error: Exception | None = None
        for candidate in order:
            candidate_kind = self.get_provider_kind(candidate)
            try:
                if candidate_kind == "anthropic":
                    return self._repair_anthropic(
                        repair_prompt, repair_system, max_tokens, provider=candidate
                    )
                if candidate_kind == "ollama":
                    return self._repair_ollama(
                        repair_prompt, repair_system, max_tokens, provider=candidate
                    )
                return self._repair_openai(
                    repair_prompt, repair_system, max_tokens, provider=candidate
                )
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise LLMError(str(last_error), provider=provider, retriable=True)
        raise LLMError("Nenhum provider disponível para repair", provider=provider, retriable=False)

    def _repair_ollama(
        self,
        repair_prompt: str,
        system_prompt: str,
        max_tokens: int,
        provider: str = "ollama",
    ) -> str:
        """Repair via provider OpenAI-compatible local/cloud."""
        try:
            openai_client = self.get_openai_client(provider)
        except ValueError as exc:
            raise LLMError(
                "Nenhum provider disponível para repair",
                provider=provider,
                retriable=False,
            ) from exc
        repair_candidates: list[str] = []
        if provider == "ollama":
            for model in self._iter_ollama_repair_models():
                if model and model not in repair_candidates:
                    repair_candidates.append(model)
        else:
            preferred_repair = self.get_provider_model(provider, "repair")
            if preferred_repair and preferred_repair not in repair_candidates:
                repair_candidates.append(preferred_repair)
            default_model = self.get_provider_model(provider, "default")
            if default_model and default_model not in repair_candidates:
                repair_candidates.append(default_model)

        if not repair_candidates:
            raise LLMError(
                f"Provider '{provider}' sem modelo de repair configurado",
                provider=provider,
                retriable=False,
            )

        last_error: Exception | None = None
        for model in repair_candidates:

            def _do_call(m: str = model) -> str:
                response = openai_client.chat.completions.create(
                    model=m,
                    max_completion_tokens=max_tokens,
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": repair_prompt},
                    ],
                )
                return response.choices[0].message.content or ""

            try:
                return self._call_with_retry(_do_call, provider=provider, action="repair_yaml")
            except Exception as exc:  # Intentional: catch-all for retry/fallback logic
                last_error = exc
                logger.warning(
                    "Repair com modelo '%s' falhou: %s",
                    model,
                    exc,
                    extra={"provider": provider, "action": "repair", "model": model},
                )

        if provider == "ollama" and self.openai is not None:
            try:
                return self._repair_openai(
                    repair_prompt,
                    system_prompt,
                    max_tokens,
                    provider="openai",
                )
            except Exception as exc:
                last_error = exc

        if provider == "ollama" and self.anthropic is not None:
            try:
                return self._repair_anthropic(
                    repair_prompt,
                    system_prompt,
                    max_tokens,
                    provider="anthropic",
                )
            except Exception as exc:
                last_error = exc

        raise LLMError(str(last_error), provider=provider, retriable=True)

    def _repair_openai(
        self,
        repair_prompt: str,
        system_prompt: str,
        max_tokens: int,
        provider: str = "openai",
    ) -> str:
        """Repair via OpenAI com retry."""
        openai_client = self.get_openai_client(provider)

        def _do_call() -> str:
            response = openai_client.chat.completions.create(
                model=self.get_provider_model(provider, "repair"),
                max_completion_tokens=max_tokens,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": repair_prompt},
                ],
            )
            return response.choices[0].message.content or ""

        try:
            return self._call_with_retry(_do_call, provider=provider, action="repair_yaml")
        except _LLM_API_ERRORS as e:
            raise LLMError(str(e), provider=provider, retriable=True)

    def _repair_anthropic(
        self,
        repair_prompt: str,
        system_prompt: str,
        max_tokens: int,
        provider: str = "anthropic",
    ) -> str:
        """Repair via Anthropic com retry."""
        anthropic_client = self.get_anthropic_client(provider)

        def _do_call() -> str:
            create_message = cast(Any, anthropic_client.messages.create)
            response = create_message(
                model=self.get_provider_model(provider, "repair"),
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": repair_prompt}],
            )
            return self._extract_anthropic_text(response)

        try:
            return self._call_with_retry(_do_call, provider=provider, action="repair_yaml")
        except _LLM_API_ERRORS as e:
            raise LLMError(str(e), provider=provider, retriable=True)


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
    if getattr(llm_config, "OLLAMA_ENABLED", False):
        print(f"  Ollama cloud: {llm_config.OLLAMA_MODEL_CLOUD}")
        print(f"  Ollama cloud fallback: {llm_config.OLLAMA_MODEL_CLOUD_FALLBACK}")
        print(f"  Ollama coder: {llm_config.OLLAMA_MODEL_CODER}")
        print(f"  Ollama vision: {llm_config.OLLAMA_MODEL_VISION}")

    print("\nEstrategia:")
    print(f"  Two-pass: {llm_config.USE_TWO_PASS}")
    print(f"  Primary: {llm_config.PRIMARY_PROVIDER}")
