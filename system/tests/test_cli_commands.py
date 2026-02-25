from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_cli_module():
    cli_path = Path(__file__).resolve().parents[1] / "cli.py"
    spec = importlib.util.spec_from_file_location("saec_cli_test", cli_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_calls_extract_with_explicit_dry_run_false(monkeypatch) -> None:
    cli = _load_cli_module()
    called: dict[str, object] = {}

    def _fake_extract(*, article=None, strategy="local_first", dry_run=False):
        called["article"] = article
        called["strategy"] = strategy
        called["dry_run"] = dry_run

    monkeypatch.setattr(cli, "extract", _fake_extract)

    cli.run(
        article="ART_001",
        strategy="local_first",
        skip_ingest=True,
        skip_validate=True,
        skip_consolidate=True,
    )

    assert called["article"] == "ART_001"
    assert called["strategy"] == "local_first"
    assert called["dry_run"] is False


def test_validate_uses_validate_yaml(monkeypatch, tmp_path: Path) -> None:
    cli = _load_cli_module()
    config_mod = importlib.import_module("src.config")
    validators_mod = importlib.import_module("src.validators")

    yamls_dir = tmp_path / "yamls"
    yamls_dir.mkdir(parents=True)
    yaml_file = yamls_dir / "ART_001.yaml"
    yaml_file.write_text("ArtigoID: ART_001\n", encoding="utf-8")

    monkeypatch.setattr(config_mod, "paths", SimpleNamespace(YAMLS=yamls_dir), raising=False)

    calls: list[str] = []

    class _Result:
        is_valid = True
        errors: list[str] = []
        warnings: list[str] = []

    def _fake_validate_yaml(content: str):
        calls.append(content)
        return _Result()

    monkeypatch.setattr(validators_mod, "validate_yaml", _fake_validate_yaml)

    cli.validate(article="ART_001", output=None)

    assert len(calls) == 1
    assert "ArtigoID" in calls[0]


def test_consolidate_calls_output_excel_kwarg(monkeypatch, tmp_path: Path) -> None:
    cli = _load_cli_module()
    config_mod = importlib.import_module("src.config")
    consolidate_mod = importlib.import_module("src.consolidate")

    yamls_dir = tmp_path / "yamls"
    consolidated_dir = tmp_path / "consolidated"
    yamls_dir.mkdir(parents=True)
    consolidated_dir.mkdir(parents=True)

    monkeypatch.setattr(
        config_mod,
        "paths",
        SimpleNamespace(YAMLS=yamls_dir, CONSOLIDATED=consolidated_dir),
        raising=False,
    )

    captured: dict[str, object] = {}

    def _fake_consolidate_yamls(**kwargs):
        captured.update(kwargs)
        return {"total_articles": 0}

    monkeypatch.setattr(consolidate_mod, "consolidate_yamls", _fake_consolidate_yamls)

    cli.consolidate(output=None)

    assert captured.get("yamls_dir") == yamls_dir
    assert captured.get("output_excel") == consolidated_dir / "SAEC_Consolidated.xlsx"
    assert "output_path" not in captured
