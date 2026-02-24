from __future__ import annotations

import json
from pathlib import Path

from profile_engine.project_profiles import import_profile_yaml
from validators import validate_yaml


def _init_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "config" / "profiles").mkdir(parents=True, exist_ok=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "project_id": "dyn",
                "name": "dyn",
                "created_at": "2026-02-19T00:00:00+00:00",
                "profile_required": True,
            }
        ),
        encoding="utf-8",
    )
    return project


def test_validate_yaml_uses_active_non_cimo_profile(tmp_path: Path, monkeypatch) -> None:
    project = _init_project(tmp_path)
    profile_yaml = tmp_path / "dynamic.yaml"
    profile_yaml.write_text(
        """
profile:
  meta:
    profile_id: "custom_generic_v1"
    version: "1.0.0"
    name: "Custom Generic"
  fields:
    - id: "ArtigoID"
      label: "ArtigoID"
      section: "metadata"
      type: "string"
      required: true
    - id: "TemaPrincipal"
      label: "TemaPrincipal"
      section: "custom"
      type: "enum"
      required: true
      allowed_values: ["A", "B"]
  rules:
    - id: "R1"
      severity: "error"
      when: "True"
      assert: "regex(get('ArtigoID'), '^ART_[0-9]{3}$')"
      message: "ArtigoID inválido"
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
    import_profile_yaml(project, yaml_path=profile_yaml, activate=True)
    monkeypatch.setenv("SAEC_EXTRACTION_PATH", str(project))

    valid_yaml = """
ArtigoID: "ART_001"
TemaPrincipal: "A"
"""
    invalid_yaml = """
ArtigoID: "BAD_001"
TemaPrincipal: "Z"
"""

    valid_result = validate_yaml(valid_yaml)
    invalid_result = validate_yaml(invalid_yaml)

    assert valid_result.is_valid is True
    assert invalid_result.is_valid is False
    assert any("TemaPrincipal" in err for err in invalid_result.errors)
