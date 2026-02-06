"""Classify pipeline subprocess errors into user-friendly messages."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassifiedError:
    category: str
    message: str
    suggestion: str


_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex_pattern, category, user_message, suggestion)
    (
        r"ModuleNotFoundError: No module named ['\"](\w+)['\"]",
        "missing_dependency",
        "Missing Python package: {match}",
        "Install the missing package with: pip install {match}",
    ),
    (
        r"ConnectionError|ConnectionRefusedError|ConnectTimeout",
        "connection",
        "Cannot connect to external service",
        "Check that Ollama is running or API endpoints are reachable.",
    ),
    (
        r"requests\.exceptions\.Timeout|ReadTimeout|ConnectTimeout",
        "timeout",
        "Request to external API timed out",
        "The API server may be overloaded. Try again later.",
    ),
    (
        r"yaml\.YAMLError|yaml\.scanner\.ScannerError",
        "yaml_error",
        "Malformed YAML in extraction output",
        "The LLM produced invalid YAML. Try re-running the extraction.",
    ),
    (
        r"FileNotFoundError:.*\.pdf",
        "pdf_not_found",
        "PDF file not found",
        "Ensure the PDF exists in the project's inputs/articles/ folder.",
    ),
    (
        r"FileNotFoundError",
        "file_not_found",
        "Required file not found",
        "Check that all input files and configuration are in place.",
    ),
    (
        r"PermissionError",
        "permission",
        "Access denied to file or directory",
        "Check file permissions or close any program using the files.",
    ),
    (
        r"OutOfMemoryError|torch\.cuda\.OutOfMemoryError|CUDA out of memory",
        "gpu_memory",
        "GPU ran out of memory",
        "Try a smaller model or close other GPU-intensive programs.",
    ),
    (
        r"RateLimitError|rate_limit|429",
        "rate_limit",
        "API rate limit exceeded",
        "Wait a few minutes before retrying. Consider using local models.",
    ),
    (
        r"AuthenticationError|401|Invalid API key|invalid_api_key",
        "auth_error",
        "API authentication failed",
        "Check your API key in the project .env file.",
    ),
    (
        r"KeyError|IndexError|AttributeError",
        "code_error",
        "Internal processing error",
        "This may be a bug. Check the full logs for details.",
    ),
]

_EXIT_CODE_MESSAGES: dict[int, ClassifiedError] = {
    0: ClassifiedError("success", "Completed successfully", ""),
    -1: ClassifiedError("cancelled", "Cancelled by user", ""),
    -2: ClassifiedError("timeout", "Job timed out", "Increase timeout or process fewer articles."),
    -99: ClassifiedError("runner_error", "Job runner failed to start", "Check that Python and dependencies are installed."),
}


def classify_error(
    *, output_lines: list[str], return_code: int | None
) -> ClassifiedError:
    """Classify a pipeline error from its output and return code.

    Args:
        output_lines: Lines of stdout/stderr from the subprocess.
        return_code: Process exit code (None if unknown).

    Returns:
        A ClassifiedError with category, message, and suggestion.
    """
    # Check exit code first
    if return_code is not None and return_code in _EXIT_CODE_MESSAGES:
        return _EXIT_CODE_MESSAGES[return_code]

    # Scan output lines (reverse order - most recent errors are more relevant)
    combined = "\n".join(output_lines[-50:])  # Last 50 lines
    for pattern, category, message_template, suggestion in _PATTERNS:
        match = re.search(pattern, combined)
        if match:
            # Use first capture group if available for the message
            match_text = match.group(1) if match.lastindex else match.group(0)
            message = message_template.format(match=match_text)
            suggestion = suggestion.format(match=match_text)
            return ClassifiedError(
                category=category,
                message=message,
                suggestion=suggestion,
            )

    # Fallback
    if return_code is not None and return_code != 0:
        return ClassifiedError(
            "unknown",
            f"Pipeline exited with code {return_code}",
            "Check the full logs for details.",
        )

    return ClassifiedError("unknown", "Unknown error", "Check the logs for details.")
