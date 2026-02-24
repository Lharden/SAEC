"""Tests for SAEC exception hierarchy."""

from __future__ import annotations

import pytest

from exceptions import (
    SAECError,
    ConfigurationError,
    PipelineError,
    IngestError,
    ExtractError,
    ValidationError,
    LLMError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_saec_error_is_exception(self):
        """Test that SAECError is a subclass of Exception."""
        assert issubclass(SAECError, Exception)

    def test_configuration_error_is_saec_error(self):
        """Test that ConfigurationError inherits from SAECError."""
        assert issubclass(ConfigurationError, SAECError)

    def test_pipeline_error_is_saec_error(self):
        """Test that PipelineError inherits from SAECError."""
        assert issubclass(PipelineError, SAECError)

    def test_ingest_error_is_pipeline_error(self):
        """Test that IngestError inherits from PipelineError."""
        assert issubclass(IngestError, PipelineError)
        assert issubclass(IngestError, SAECError)

    def test_extract_error_is_pipeline_error(self):
        """Test that ExtractError inherits from PipelineError."""
        assert issubclass(ExtractError, PipelineError)
        assert issubclass(ExtractError, SAECError)

    def test_validation_error_is_pipeline_error(self):
        """Test that ValidationError inherits from PipelineError."""
        assert issubclass(ValidationError, PipelineError)
        assert issubclass(ValidationError, SAECError)

    def test_llm_error_is_extract_error(self):
        """Test that LLMError inherits from ExtractError."""
        assert issubclass(LLMError, ExtractError)
        assert issubclass(LLMError, PipelineError)
        assert issubclass(LLMError, SAECError)


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_can_raise_and_catch(self):
        """Test that ConfigurationError can be raised and caught."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Missing API key")

    def test_message_preserved(self):
        """Test that error message is preserved."""
        msg = "Test configuration error"
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError(msg)
        assert str(exc_info.value) == msg


class TestLLMError:
    """Tests for LLMError with provider and retriable attributes."""

    def test_llm_error_has_provider_attribute(self):
        """Test that LLMError has a provider attribute."""
        error = LLMError("Connection failed", provider="anthropic")
        assert error.provider == "anthropic"

    def test_llm_error_has_retriable_attribute(self):
        """Test that LLMError has a retriable attribute."""
        error = LLMError("Timeout", retriable=True)
        assert error.retriable is True

    def test_llm_error_defaults(self):
        """Test LLMError default values for provider and retriable."""
        error = LLMError("Some error")
        assert error.provider == ""
        assert error.retriable is False

    def test_llm_error_can_be_raised_and_caught(self):
        """Test that LLMError can be raised and caught."""
        with pytest.raises(LLMError):
            raise LLMError("API rate limit exceeded", provider="openai", retriable=True)

    def test_llm_error_message_preserved(self):
        """Test that LLMError message is preserved."""
        msg = "Test LLM error message"
        with pytest.raises(LLMError) as exc_info:
            raise LLMError(msg)
        assert str(exc_info.value) == msg

    def test_llm_error_attributes_preserved_after_raise(self):
        """Test that provider and retriable are preserved after raising."""
        error = LLMError("Rate limit", provider="anthropic", retriable=True)
        try:
            raise error
        except LLMError as caught:
            assert caught.provider == "anthropic"
            assert caught.retriable is True


class TestIngestError:
    """Tests for IngestError."""

    def test_ingest_error_can_be_raised(self):
        """Test that IngestError can be raised."""
        with pytest.raises(IngestError):
            raise IngestError("PDF file not found")

    def test_ingest_error_message(self):
        """Test IngestError message is preserved."""
        msg = "Failed to read PDF"
        with pytest.raises(IngestError) as exc_info:
            raise IngestError(msg)
        assert str(exc_info.value) == msg


class TestExtractError:
    """Tests for ExtractError."""

    def test_extract_error_can_be_raised(self):
        """Test that ExtractError can be raised."""
        with pytest.raises(ExtractError):
            raise ExtractError("LLM returned invalid YAML")

    def test_extract_error_message(self):
        """Test ExtractError message is preserved."""
        msg = "Extraction failed"
        with pytest.raises(ExtractError) as exc_info:
            raise ExtractError(msg)
        assert str(exc_info.value) == msg


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_can_be_raised(self):
        """Test that ValidationError can be raised."""
        with pytest.raises(ValidationError):
            raise ValidationError("YAML schema validation failed")

    def test_validation_error_message(self):
        """Test ValidationError message is preserved."""
        msg = "Invalid YAML structure"
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError(msg)
        assert str(exc_info.value) == msg


class TestPipelineError:
    """Tests for PipelineError."""

    def test_pipeline_error_can_be_raised(self):
        """Test that PipelineError can be raised."""
        with pytest.raises(PipelineError):
            raise PipelineError("Pipeline execution failed")

    def test_pipeline_error_message(self):
        """Test PipelineError message is preserved."""
        msg = "Pipeline error"
        with pytest.raises(PipelineError) as exc_info:
            raise PipelineError(msg)
        assert str(exc_info.value) == msg


class TestCatchingExceptions:
    """Tests for catching exceptions at different levels."""

    def test_catch_saec_error_catches_all_saec_errors(self):
        """Test catching SAECError catches all derived exceptions."""
        exceptions = [
            ConfigurationError("config"),
            PipelineError("pipeline"),
            IngestError("ingest"),
            ExtractError("extract"),
            ValidationError("validation"),
            LLMError("llm"),
        ]
        for exc in exceptions:
            with pytest.raises(SAECError):
                raise exc

    def test_catch_pipeline_error_catches_specific_errors(self):
        """Test catching PipelineError catches derived errors."""
        exceptions = [
            IngestError("ingest"),
            ExtractError("extract"),
            ValidationError("validation"),
            LLMError("llm"),
        ]
        for exc in exceptions:
            with pytest.raises(PipelineError):
                raise exc

    def test_catch_extract_error_catches_llm_error(self):
        """Test catching ExtractError also catches LLMError."""
        with pytest.raises(ExtractError):
            raise LLMError("llm error")
