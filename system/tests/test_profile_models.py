from __future__ import annotations

from profile_engine.models import ProfileField, ProfileMeta, ProfileRule, ProfileSpec


def test_profile_field_from_dict_parses_lists_and_defaults() -> None:
    field = ProfileField.from_dict(
        {
            "id": "ClasseIA",
            "label": "Classe IA",
            "section": "intervention",
            "type": "enum",
            "allowed_values": ["Predictive", "Generative"],
            "aliases": ["classe", "ai_class"],
            "required": "true",
        }
    )

    assert field.field_id == "ClasseIA"
    assert field.required is True
    assert field.allowed_values == ("Predictive", "Generative")
    assert field.aliases == ("classe", "ai_class")


def test_profile_spec_field_lookup_supports_alias() -> None:
    spec = ProfileSpec(
        schema_version="1.0",
        meta=ProfileMeta(profile_id="p1", version="1.0.0", name="Profile"),
        topics=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).topics,
        fields=(
            ProfileField.from_dict(
                {
                    "id": "ArtigoID",
                    "section": "metadata",
                    "type": "string",
                    "aliases": ["id_artigo"],
                }
            ),
        ),
        rules=(),
        quotes_policy=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).quotes_policy,
        output=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).output,
        prompt_contract=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).prompt_contract,
    )

    assert spec.field_by_id("ArtigoID") is not None
    assert spec.field_by_id("id_artigo") is not None


def test_profile_spec_validate_structure_flags_common_issues() -> None:
    spec = ProfileSpec(
        schema_version="1.0",
        meta=ProfileMeta(profile_id="", version="", name=""),
        topics=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).topics,
        fields=(
            ProfileField.from_dict(
                {"id": "CampoA", "section": "metadata", "type": "unknown_type"}
            ),
        ),
        rules=(ProfileRule.from_dict({"id": "R1", "severity": "fatal", "assert": ""}),),
        quotes_policy=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).quotes_policy,
        output=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).output,
        prompt_contract=ProfileSpec.from_dict({"profile": {"fields": [{"id": "ArtigoID"}]}}).prompt_contract,
    )

    errors = spec.validate_structure()

    assert any("profile.meta.profile_id is required" in e for e in errors)
    assert any("must include 'ArtigoID'" in e for e in errors)
    assert any("invalid type" in e for e in errors)
    assert any("invalid severity" in e for e in errors)

