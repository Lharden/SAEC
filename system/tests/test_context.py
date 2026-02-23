from __future__ import annotations

import logging
from pathlib import Path

import context as app_context


def test_default_artigo_id_filter_injects_missing_fields() -> None:
    filt = app_context._DefaultArtigoIdFilter()
    record = logging.LogRecord(
        name="saec",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )

    assert filt.filter(record) is True
    assert record.artigo_id == "-"
    assert record.provider == "-"
    assert record.action == "-"


def test_setup_logging_is_idempotent_and_creates_file_handler(tmp_path: Path) -> None:
    logger = logging.getLogger("saec")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    log_path = tmp_path / "logs" / "saec.log"
    configured = app_context.setup_logging(log_level="DEBUG", log_path=log_path, console=False)

    assert configured is logger
    assert configured.level == logging.DEBUG
    assert len(configured.handlers) == 1

    configured.info("line", extra={"artigo_id": "ART_001", "provider": "openai", "action": "test"})
    for handler in configured.handlers:
        handler.flush()
    assert log_path.exists()

    configured_again = app_context.setup_logging(log_level="WARNING", log_path=log_path, console=False)
    assert configured_again is configured
    assert configured_again.level == logging.WARNING
    assert len(configured_again.handlers) == 1


def test_make_context_builds_app_context(monkeypatch, tmp_path: Path) -> None:
    class DummyPaths:
        def __init__(self) -> None:
            self.EXTRACTION = tmp_path / "Extraction"

    class DummyLLMConfig:
        pass

    class DummyExtractionConfig:
        pass

    fake_logger = logging.getLogger("saec-test")
    monkeypatch.setattr(app_context, "Paths", DummyPaths)
    monkeypatch.setattr(app_context, "LLMConfig", DummyLLMConfig)
    monkeypatch.setattr(app_context, "ExtractionConfig", DummyExtractionConfig)
    monkeypatch.setattr(
        app_context,
        "setup_logging",
        lambda **_: fake_logger,
    )

    ctx = app_context.make_context(log_level="INFO")

    assert isinstance(ctx, app_context.AppContext)
    assert isinstance(ctx.paths, DummyPaths)
    assert isinstance(ctx.llm_config, DummyLLMConfig)
    assert isinstance(ctx.extraction_config, DummyExtractionConfig)
    assert ctx.logger is fake_logger
