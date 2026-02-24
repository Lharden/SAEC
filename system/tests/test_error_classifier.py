from __future__ import annotations

import pytest

from error_classifier import classify_error


@pytest.mark.parametrize(
    ("return_code", "category", "message_snippet"),
    [
        (0, "success", "Completed successfully"),
        (1, "pipeline_error", "Pipeline error"),
        (-1, "cancelled", "Cancelled by user"),
        (-15, "cancelled", "Cancelled by user"),
        (-2, "timeout", "Job timed out"),
        (-99, "runner_error", "Job runner failed to start"),
    ],
)
def test_classify_error_from_exit_code(
    return_code: int, category: str, message_snippet: str
) -> None:
    result = classify_error(output_lines=["irrelevant"], return_code=return_code)
    assert result.category == category
    assert message_snippet in result.message


@pytest.mark.parametrize(
    ("line", "category", "message_snippet", "suggestion_snippet"),
    [
        (
            "ModuleNotFoundError: No module named 'yaml'",
            "missing_dependency",
            "Missing Python package: yaml",
            "pip install yaml",
        ),
        (
            "ConnectionError: failed to connect",
            "connection",
            "Cannot connect to external service",
            "Ollama",
        ),
        (
            "requests.exceptions.Timeout: request timeout",
            "timeout",
            "timed out",
            "Try again later",
        ),
        (
            "yaml.YAMLError: malformed",
            "yaml_error",
            "Malformed YAML",
            "invalid YAML",
        ),
        (
            "FileNotFoundError: article.pdf",
            "pdf_not_found",
            "PDF file not found",
            "inputs/articles",
        ),
        (
            "FileNotFoundError: config not found",
            "file_not_found",
            "Required file not found",
            "configuration",
        ),
        (
            "PermissionError: [Errno 13] Access denied",
            "permission",
            "Access denied",
            "permissions",
        ),
        (
            "CUDA out of memory",
            "gpu_memory",
            "out of memory",
            "smaller model",
        ),
        (
            "RateLimitError: 429 too many requests",
            "rate_limit",
            "rate limit exceeded",
            "Wait a few minutes",
        ),
        (
            "AuthenticationError: Invalid API key",
            "auth_error",
            "authentication failed",
            "API key",
        ),
        (
            "KeyError: 'missing_field'",
            "code_error",
            "Internal processing error",
            "bug",
        ),
    ],
)
def test_classify_error_from_output_patterns(
    line: str, category: str, message_snippet: str, suggestion_snippet: str
) -> None:
    result = classify_error(output_lines=["prefix", line], return_code=42)
    assert result.category == category
    assert message_snippet in result.message
    assert suggestion_snippet in result.suggestion


def test_classify_error_unknown_fallback_for_non_zero_code() -> None:
    result = classify_error(output_lines=["n/a"], return_code=7)
    assert result.category == "unknown"
    assert "code 7" in result.message
