from __future__ import annotations

from profile_engine.models import (
    OutputContract,
    ProfileField,
    ProfileMeta,
    ProfileRule,
    ProfileSpec,
    PromptContract,
    QuotePolicy,
    TopicConfig,
)
from profile_engine.validator import (
    _evaluate_rule_expr,
    evaluate_profile_rules,
    validate_dict_with_profile,
    validate_rule_expression,
)


def _build_profile(*, rules: tuple[ProfileRule, ...] = ()) -> ProfileSpec:
    return ProfileSpec(
        schema_version="1.0",
        meta=ProfileMeta(profile_id="p", version="1.0.0", name="Profile"),
        topics=TopicConfig(),
        fields=(
            ProfileField.from_dict(
                {"id": "ArtigoID", "section": "metadata", "type": "string", "required": True}
            ),
            ProfileField.from_dict(
                {"id": "ClasseIA", "section": "intervention", "type": "enum", "allowed_values": ["A", "B"]}
            ),
        ),
        rules=rules,
        quotes_policy=QuotePolicy(enabled=False),
        output=OutputContract(),
        prompt_contract=PromptContract(),
    )


def test_validate_rule_expression_rejects_unsafe_nodes() -> None:
    err = validate_rule_expression("__import__('os').system('x')")
    assert err is not None


def test_evaluate_rule_expr_returns_false_on_runtime_error() -> None:
    assert _evaluate_rule_expr("regex('abc', '[')", {}) is False


def test_evaluate_profile_rules_applies_when_and_assert() -> None:
    rules = (
        ProfileRule.from_dict(
            {"id": "R1", "severity": "error", "when": "True", "assert": "eq(get('ArtigoID'), 'ART_001')", "message": "id"}
        ),
        ProfileRule.from_dict(
            {"id": "R2", "severity": "warning", "when": "False", "assert": "False", "message": "skip"}
        ),
    )

    outcomes = evaluate_profile_rules(rules, {"ArtigoID": "ART_001"})

    assert outcomes[0].passed is True
    assert outcomes[1].passed is True


def test_validate_dict_with_profile_reports_field_and_rule_errors() -> None:
    rules = (
        ProfileRule.from_dict(
            {"id": "R10", "severity": "error", "when": "True", "assert": "eq(get('ClasseIA'), 'A')", "message": "classe invalida"}
        ),
    )
    profile = _build_profile(rules=rules)
    payload = {"ArtigoID": "", "ClasseIA": "C"}

    errors, warnings, passed, failed = validate_dict_with_profile(payload, profile)

    assert any("required field is empty" in e for e in errors)
    assert any("[R10]" in e for e in errors)
    assert warnings == []
    assert passed == []
    assert failed == [10]
