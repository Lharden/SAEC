from __future__ import annotations

import json
from pathlib import Path

import pytest

from profile_engine.project_profiles import (
    bootstrap_profile,
    get_active_profile_ref,
    has_active_profile,
    import_profile_yaml,
    load_active_profile_spec,
    snapshot_active_profile_for_run,
)
from profile_engine.loader import ProfileLoadError, load_profile_spec
from profile_engine.models import CURRENT_PROFILE_SCHEMA_VERSION


def _init_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    (project_root / "config" / "profiles").mkdir(parents=True, exist_ok=True)
    manifest = {
        "project_id": "tmp",
        "name": "tmp",
        "created_at": "2026-02-19T00:00:00+00:00",
        "profile_required": True,
    }
    (project_root / "project.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    return project_root


def test_bootstrap_profile_activates_cimo_profile(tmp_path: Path) -> None:
    project_root = _init_project(tmp_path)

    ref = bootstrap_profile(project_root, profile_id="cimo_v3_3", activate=True)

    assert ref.profile_id == "cimo_v3_3"
    assert has_active_profile(project_root) is True
    active = get_active_profile_ref(project_root)
    assert active is not None
    assert active.profile_id == "cimo_v3_3"

    spec, _loaded_ref = load_active_profile_spec(project_root)
    assert spec.meta.profile_id == "cimo_v3_3"


def test_import_profile_yaml_creates_active_version(tmp_path: Path) -> None:
    project_root = _init_project(tmp_path)
    profile_yaml = tmp_path / "mini_profile.yaml"
    profile_yaml.write_text(
        """
profile:
  meta:
    profile_id: "mini_profile"
    version: "1.0.0"
    name: "Mini"
  fields:
    - id: "ArtigoID"
      label: "ArtigoID"
      section: "metadata"
      type: "string"
      required: true
  rules: []
  quotes_policy:
    enabled: false
  output:
    format: "yaml"
  prompt_contract:
    return_only_output: true
    include_self_review: false
""".strip(),
        encoding="utf-8",
    )

    ref = import_profile_yaml(project_root, yaml_path=profile_yaml, activate=True)

    assert ref.profile_id == "mini_profile"
    assert ref.profile_path.exists()
    assert has_active_profile(project_root) is True


def test_import_invalid_profile_raises(tmp_path: Path) -> None:
    project_root = _init_project(tmp_path)
    invalid_yaml = tmp_path / "invalid_profile.yaml"
    invalid_yaml.write_text(
        """
profile:
  meta:
    profile_id: ""
    version: ""
    name: ""
  fields: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        import_profile_yaml(project_root, yaml_path=invalid_yaml, activate=True)


def test_legacy_profile_without_schema_version_is_migrated(tmp_path: Path) -> None:
    project_root = _init_project(tmp_path)
    legacy_yaml = tmp_path / "legacy_profile.yaml"
    legacy_yaml.write_text(
        """
profile:
  meta:
    profile_id: "legacy_profile"
    version: "0.9.0"
    name: "Legacy"
  fields:
    - field_id: "ArtigoID"
      section: "metadata"
      kind: "string"
      required: true
  rules:
    - rule_id: "R1"
      severity: "error"
      if: "True"
      assert_expr: "regex(get('ArtigoID'), '^ART_[0-9]{3}$')"
      message: "id invalido"
  quotes:
    enabled: false
  output:
    format: "yaml"
""".strip(),
        encoding="utf-8",
    )

    ref = import_profile_yaml(project_root, yaml_path=legacy_yaml, activate=True)
    spec, _ = load_active_profile_spec(project_root)

    assert ref.schema_version == CURRENT_PROFILE_SCHEMA_VERSION
    assert spec.schema_version == CURRENT_PROFILE_SCHEMA_VERSION
    assert spec.field_by_id("ArtigoID") is not None
    assert spec.rules[0].rule_id == "R1"


def test_profile_loader_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    bad_schema_yaml = tmp_path / "bad_schema.yaml"
    bad_schema_yaml.write_text(
        """
schema_version: "99.0"
profile:
  meta:
    profile_id: "bad_schema"
    version: "1.0.0"
    name: "Bad"
  fields:
    - id: "ArtigoID"
      label: "ArtigoID"
      section: "metadata"
      type: "string"
      required: true
  rules: []
  quotes_policy:
    enabled: false
  output:
    format: "yaml"
  prompt_contract:
    return_only_output: true
    include_self_review: false
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProfileLoadError):
        load_profile_spec(bad_schema_yaml)


def test_profile_snapshot_is_saved_under_outputs_consolidated(tmp_path: Path) -> None:
    project_root = _init_project(tmp_path)
    ref = bootstrap_profile(project_root, profile_id="cimo_v3_3", activate=True)
    output_root = project_root / "outputs" / "consolidated"
    output_root.mkdir(parents=True, exist_ok=True)

    snapshot = snapshot_active_profile_for_run(
        project_root,
        output_root=output_root,
        run_id="test_run_001",
        command="--step 3",
        force=False,
        dry_run=False,
    )

    assert snapshot.profile_yaml_path.exists()
    assert snapshot.metadata_path.exists()
    if ref.prompt_path is not None:
        assert snapshot.prompt_path is not None
        assert snapshot.prompt_path.exists()

    payload = json.loads(snapshot.metadata_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "test_run_001"
    assert payload["active_profile"]["profile_id"] == "cimo_v3_3"
    assert payload["active_profile"]["schema_version"] == CURRENT_PROFILE_SCHEMA_VERSION


def test_import_profile_with_invalid_rule_expression_fails(tmp_path: Path) -> None:
    project_root = _init_project(tmp_path)
    invalid_rule_yaml = tmp_path / "invalid_rule.yaml"
    invalid_rule_yaml.write_text(
        """
profile:
  meta:
    profile_id: "invalid_rule"
    version: "1.0.0"
    name: "Invalid Rule"
  fields:
    - id: "ArtigoID"
      label: "ArtigoID"
      section: "metadata"
      type: "string"
      required: true
  rules:
    - id: "R1"
      severity: "error"
      when: "True"
      assert: "unknown_func(get('ArtigoID'))"
      message: "bad expr"
  quotes_policy:
    enabled: false
  output:
    format: "yaml"
  prompt_contract:
    return_only_output: true
    include_self_review: false
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        import_profile_yaml(project_root, yaml_path=invalid_rule_yaml, activate=True)

