from __future__ import annotations

import io
import logging

import pytest

from log_config import setup_logging


@pytest.fixture(autouse=True)
def _cleanup_managed_handlers() -> None:
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        if not getattr(handler, "_saec_managed", False):
            continue
        root.removeHandler(handler)
        handler.close()


def _managed_handlers() -> list[logging.Handler]:
    root = logging.getLogger()
    return [h for h in root.handlers if getattr(h, "_saec_managed", False)]


def test_setup_logging_replaces_only_managed_handlers(tmp_path) -> None:
    root = logging.getLogger()
    unmanaged = logging.StreamHandler(io.StringIO())
    root.addHandler(unmanaged)

    try:
        setup_logging(log_dir=tmp_path, gui_callback=lambda _line: None, level=logging.INFO)
        first_managed = list(_managed_handlers())
        first_file = next(
            handler
            for handler in first_managed
            if getattr(handler, "_saec_managed_kind", "") == "file"
        )

        setup_logging(log_dir=tmp_path, gui_callback=lambda _line: None, level=logging.DEBUG)

        assert unmanaged in root.handlers
        assert first_file not in root.handlers
        assert getattr(first_file, "stream", None) is None

        managed = _managed_handlers()
        assert sum(
            1
            for handler in managed
            if getattr(handler, "_saec_managed_kind", "") == "file"
        ) == 1
        assert sum(
            1
            for handler in managed
            if getattr(handler, "_saec_managed_kind", "") == "gui"
        ) == 1
        assert sum(
            1
            for handler in managed
            if getattr(handler, "_saec_managed_kind", "") == "stream"
        ) == 1
    finally:
        root.removeHandler(unmanaged)
        unmanaged.close()


def test_setup_logging_keeps_single_managed_stream_fallback() -> None:
    setup_logging(log_dir=None, gui_callback=None, level=logging.INFO)
    setup_logging(log_dir=None, gui_callback=None, level=logging.INFO)

    managed_streams = [
        handler
        for handler in _managed_handlers()
        if getattr(handler, "_saec_managed_kind", "") == "stream"
    ]
    assert len(managed_streams) == 1
