"""Tipos e utilidades de retry para o cliente LLM."""

from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar, cast
import random
import time

try:  # Optional imports for robust retry detection
    import httpx
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    import anthropic
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    anthropic = None  # type: ignore[assignment]

try:
    import openai
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    openai = None  # type: ignore[assignment]

_F = TypeVar("_F", bound=Callable[..., str])
Provider = str

try:
    from . import exceptions as _exceptions
except (ImportError, ModuleNotFoundError):  # pragma: no cover - standalone usage
    import exceptions as _exceptions

LLMError = _exceptions.LLMError


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.25,
    max_elapsed: float = 120.0,
) -> Callable[[_F], _F]:
    """Decorator para retry com backoff exponencial."""

    def decorator(func: _F) -> _F:
        @wraps(func)
        def wrapper(*args: object, **kwargs: object) -> str:
            last_exception: Exception | None = None
            started = time.monotonic()

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if not is_retriable(e) or attempt == max_retries:
                        raise

                    elapsed = time.monotonic() - started
                    if elapsed >= max_elapsed:
                        raise

                    # Calcular delay com backoff exponencial + jitter
                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    if jitter > 0:
                        delay = delay + random.uniform(0, delay * jitter)
                    time.sleep(delay)

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry failed without captured exception")

        return cast(_F, wrapper)

    return decorator


def is_retriable(exc: Exception) -> bool:
    """Decide se o erro pode ser reprocessado."""
    # LLMError explicit
    if isinstance(exc, LLMError):
        return bool(getattr(exc, "retriable", False))

    # Typed exceptions
    if httpx is not None:
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
            return True

    if anthropic is not None:
        if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError)):
            return True

    if openai is not None:
        if isinstance(exc, openai.RateLimitError):
            return True

    # status_code on exception
    status_code = getattr(exc, "status_code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True

    # Some SDKs wrap status in response
    response = getattr(exc, "response", None)
    if response is not None:
        resp_status = getattr(response, "status_code", None)
        if resp_status in (429, 500, 502, 503, 504):
            return True

    # Fallback by message
    msg = str(exc).lower()
    if any(k in msg for k in ("rate", "limit", "timeout", "connection", "502", "503", "504")):
        return True

    return False
