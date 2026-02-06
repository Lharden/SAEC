"""Custom exceptions for SAEC-O&G."""

from __future__ import annotations


class SAECError(Exception):
    """Base exception for the system."""


class ConfigurationError(SAECError):
    """Configuration errors (paths, API keys, env)."""


class PipelineError(SAECError):
    """Generic pipeline error."""


class IngestError(PipelineError):
    """PDF ingestion error."""


class ExtractError(PipelineError):
    """LLM extraction error."""


class ValidationError(PipelineError):
    """YAML validation error."""


class LLMError(ExtractError):
    """LLM communication error (timeout, rate limit, etc.)."""

    def __init__(self, message: str, provider: str = "", retriable: bool = False) -> None:
        super().__init__(message)
        self.provider = provider
        self.retriable = retriable
