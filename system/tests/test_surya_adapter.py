from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from adapters import surya_adapter as mod
from exceptions import IngestError


def test_normalize_text_payload_for_common_types() -> None:
    assert mod._normalize_text_payload("x") == "x"
    assert mod._normalize_text_payload(["a", "b"]) == "a\nb"
    assert "k: v" in mod._normalize_text_payload({"k": "v"})


def test_ocr_image_raises_when_surya_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(mod, "is_surya_available", lambda: False)
    with pytest.raises(IngestError, match="surya-ocr não está instalado"):
        mod.ocr_image(Image.new("RGB", (8, 8), "white"))


def test_ocr_image_success(monkeypatch) -> None:
    monkeypatch.setattr(mod, "is_surya_available", lambda: True)

    def det(_images):
        return ["detected"]

    def rec(_images, _det_results):
        return [
            SimpleNamespace(
                text_lines=[
                    SimpleNamespace(
                        text="hello world",
                        confidence=0.8,
                        bbox=[1, 2, 3, 4],
                    )
                ]
            )
        ]

    monkeypatch.setattr(mod, "_get_predictors", lambda: {"detection": det, "recognition": rec})

    out = mod.ocr_image(Image.new("RGB", (20, 10), "white"), languages=["en"])

    assert out.text == "hello world"
    assert out.confidence == pytest.approx(0.8)
    assert len(out.bboxes) == 1
    assert out.width == 20
    assert out.height == 10


def test_detect_scanned_pdf_returns_error_dict_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setitem(
        sys.modules,
        "fitz",
        SimpleNamespace(open=lambda _path: (_ for _ in ()).throw(RuntimeError("boom"))),
    )

    out = mod.detect_scanned_pdf(tmp_path / "in.pdf")

    assert out["is_likely_scanned"] is False
    assert "error" in out


def test_estimate_ocr_time_uses_gpu_benchmark(monkeypatch, tmp_path: Path) -> None:
    class _Doc:
        def __len__(self) -> int:
            return 4

        def close(self) -> None:
            return None

    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda _path: _Doc()))
    monkeypatch.setattr(mod, "is_gpu_available", lambda: True)

    out = mod.estimate_ocr_time(tmp_path / "in.pdf")

    assert out["total_pages"] == 4
    assert out["gpu_available"] is True
    assert out["estimated_total_time_sec"] == 12
