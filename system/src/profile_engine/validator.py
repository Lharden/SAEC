"""Runtime validation of extraction payloads against declarative profiles."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any

from .models import ProfileField, ProfileRule, ProfileSpec


_ALLOWED_AST_NODES = {
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.In,
    ast.NotIn,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
}


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str
    passed: bool
    severity: str
    message: str


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _validate_field_type(field: ProfileField, value: Any, errors: list[str]) -> None:
    kind = field.field_type
    if kind in {"string", "text", "enum"}:
        if not isinstance(value, str):
            errors.append(f"[FIELD:{field.field_id}] must be string")
            return
        text = value.strip()
        if field.min_length and len(text) < field.min_length:
            errors.append(
                f"[FIELD:{field.field_id}] length must be >= {field.min_length}"
            )
        if field.max_length and len(text) > field.max_length:
            errors.append(
                f"[FIELD:{field.field_id}] length must be <= {field.max_length}"
            )
        if kind == "enum" and field.allowed_values and text not in field.allowed_values:
            allowed = ", ".join(field.allowed_values)
            errors.append(
                f"[FIELD:{field.field_id}] invalid enum '{text}'. Allowed: {allowed}"
            )
        return

    if kind == "int":
        if isinstance(value, bool):
            errors.append(f"[FIELD:{field.field_id}] must be int")
            return
        try:
            int(value)
        except (TypeError, ValueError):
            errors.append(f"[FIELD:{field.field_id}] must be int")
        return

    if kind == "float":
        if isinstance(value, bool):
            errors.append(f"[FIELD:{field.field_id}] must be float")
            return
        try:
            float(value)
        except (TypeError, ValueError):
            errors.append(f"[FIELD:{field.field_id}] must be float")
        return

    if kind == "bool":
        if isinstance(value, bool):
            return
        normalized = str(value).strip().lower()
        if normalized not in {"true", "false", "1", "0", "yes", "no"}:
            errors.append(f"[FIELD:{field.field_id}] must be bool")
        return

    if kind == "list":
        if not isinstance(value, list):
            errors.append(f"[FIELD:{field.field_id}] must be list")
        return

    if kind == "object":
        if not isinstance(value, dict):
            errors.append(f"[FIELD:{field.field_id}] must be object")


def _normalize_rule_expr(expr: str) -> str:
    text = (expr or "").strip() or "True"
    text = re.sub(r"\btrue\b", "True", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfalse\b", "False", text, flags=re.IGNORECASE)
    return text


def _assert_safe_ast(expr: str) -> ast.Expression:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_AST_NODES:
            raise ValueError(f"unsupported expression node: {type(node).__name__}")
    return tree


def _validate_rule_names(tree: ast.Expression, allowed_names: set[str]) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                return "unsupported call target"
            if node.func.id not in allowed_names:
                return f"unknown function '{node.func.id}'"
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id not in allowed_names:
                return f"unknown identifier '{node.id}'"
    return None


def _rule_env(data: dict[str, Any]) -> dict[str, Any]:
    def get(field_name: str, default: Any = "") -> Any:
        return data.get(field_name, default)

    def not_empty(value: Any) -> bool:
        return not _is_empty(value)

    def empty(value: Any) -> bool:
        return _is_empty(value)

    def eq(a: Any, b: Any) -> bool:
        return a == b

    def ne(a: Any, b: Any) -> bool:
        return a != b

    def contains(value: Any, token: str) -> bool:
        return str(token) in str(value or "")

    def contains_any(value: Any, tokens: list[Any]) -> bool:
        hay = str(value or "")
        return any(str(token) in hay for token in (tokens or []))

    def contains_all(value: Any, tokens: list[Any]) -> bool:
        hay = str(value or "")
        return all(str(token) in hay for token in (tokens or []))

    def regex(value: Any, pattern: str) -> bool:
        return bool(re.search(pattern, str(value or "")))

    def single_line(value: Any) -> bool:
        return "\n" not in str(value or "").strip()

    def lower(value: Any) -> str:
        return str(value or "").lower()

    def in_set(value: Any, options: list[Any]) -> bool:
        return str(value) in {str(item) for item in (options or [])}

    def every_sentence_startswith(value: Any, prefix: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        parts = [segment.strip() for segment in re.split(r"[.;]\s*", text) if segment.strip()]
        if not parts:
            return True
        return all(segment.upper().startswith(prefix.upper()) for segment in parts)

    return {
        "True": True,
        "False": False,
        "get": get,
        "not_empty": not_empty,
        "empty": empty,
        "eq": eq,
        "ne": ne,
        "contains": contains,
        "contains_any": contains_any,
        "contains_all": contains_all,
        "regex": regex,
        "single_line": single_line,
        "lower": lower,
        "in_set": in_set,
        "every_sentence_startswith": every_sentence_startswith,
    }


def _evaluate_rule_expr(expr: str, data: dict[str, Any]) -> bool:
    text = _normalize_rule_expr(expr)
    tree = _assert_safe_ast(text)
    env = _rule_env(data)
    try:
        result = eval(compile(tree, "<profile-rule>", "eval"), {"__builtins__": {}}, env)
    except Exception:  # Intentional: eval() can raise any exception type
        return False
    return bool(result)


def validate_rule_expression(expr: str) -> str | None:
    """Validate rule expression syntax and allowed identifiers."""
    text = _normalize_rule_expr(expr)
    try:
        tree = _assert_safe_ast(text)
    except (SyntaxError, ValueError) as exc:
        return str(exc)
    allowed_names = set(_rule_env({}).keys())
    return _validate_rule_names(tree, allowed_names)


def validate_rule_expressions(rules: tuple[ProfileRule, ...]) -> list[str]:
    """Return a list of invalid rule expression errors."""
    errors: list[str] = []
    for rule in rules:
        when_error = validate_rule_expression(rule.when)
        if when_error:
            errors.append(
                f"rule '{rule.rule_id}' has invalid 'when' expression: {when_error}"
            )
        assert_error = validate_rule_expression(rule.assert_expr)
        if assert_error:
            errors.append(
                f"rule '{rule.rule_id}' has invalid 'assert' expression: {assert_error}"
            )
    return errors


def evaluate_profile_rules(
    rules: tuple[ProfileRule, ...], data: dict[str, Any]
) -> list[RuleEvaluation]:
    outcomes: list[RuleEvaluation] = []
    for rule in rules:
        should_apply = _evaluate_rule_expr(rule.when, data)
        if not should_apply:
            outcomes.append(
                RuleEvaluation(
                    rule_id=rule.rule_id,
                    passed=True,
                    severity=rule.severity,
                    message=rule.message,
                )
            )
            continue
        passed = _evaluate_rule_expr(rule.assert_expr, data)
        outcomes.append(
            RuleEvaluation(
                rule_id=rule.rule_id,
                passed=passed,
                severity=rule.severity,
                message=rule.message,
            )
        )
    return outcomes


def validate_dict_with_profile(
    data: dict[str, Any], profile: ProfileSpec
) -> tuple[list[str], list[str], list[int], list[int]]:
    """Validate one extraction dict against a profile specification."""
    errors: list[str] = []
    warnings: list[str] = []
    rules_passed: list[int] = []
    rules_failed: list[int] = []

    # Field schema validation
    for field in profile.fields:
        value = data.get(field.field_id)
        if _is_empty(value):
            if field.required:
                errors.append(f"[FIELD:{field.field_id}] required field is empty")
            continue

        if not field.multiple and isinstance(value, list):
            errors.append(f"[FIELD:{field.field_id}] does not allow multiple values")
            continue

        _validate_field_type(field, value, errors)

    # Quotes policy validation
    quote_policy = profile.quotes_policy
    if quote_policy.enabled:
        quotes = data.get("Quotes", [])
        if not isinstance(quotes, list):
            errors.append("[QUOTES] Quotes must be a list")
            quotes = []

        count = len(quotes)
        if count < quote_policy.min_quotes:
            errors.append(
                f"[QUOTES] minimum quotes is {quote_policy.min_quotes}, got {count}"
            )
        if quote_policy.max_quotes > 0 and count > quote_policy.max_quotes:
            errors.append(
                f"[QUOTES] maximum quotes is {quote_policy.max_quotes}, got {count}"
            )

        required_types_seen: set[str] = set()
        allowed_types = set(quote_policy.allowed_types)
        id_pattern = re.compile(quote_policy.quote_schema.id_pattern)

        for idx, quote in enumerate(quotes):
            if not isinstance(quote, dict):
                errors.append(f"[QUOTES] item #{idx + 1} must be object")
                continue
            for req in quote_policy.quote_schema.required_fields:
                if _is_empty(quote.get(req)):
                    errors.append(f"[QUOTES] item #{idx + 1} missing '{req}'")

            quote_id = str(quote.get("QuoteID", "")).strip()
            if quote_id and not id_pattern.match(quote_id):
                errors.append(
                    f"[QUOTES] item #{idx + 1} QuoteID '{quote_id}' does not match pattern"
                )

            tipo = str(quote.get("TipoQuote", "")).strip()
            if tipo:
                required_types_seen.add(tipo)
                if allowed_types and tipo not in allowed_types:
                    errors.append(
                        f"[QUOTES] item #{idx + 1} TipoQuote '{tipo}' is not allowed"
                    )

            trecho = str(quote.get("Trecho", "")).strip()
            if trecho and len(trecho) < quote_policy.quote_schema.trecho_min_length:
                warnings.append(
                    f"[QUOTES] item #{idx + 1} Trecho seems too short ({len(trecho)} chars)"
                )

        for required_type in quote_policy.required_types:
            if required_type not in required_types_seen:
                warnings.append(
                    f"[QUOTES] recommended quote type missing: '{required_type}'"
                )

    # Declarative business rules
    outcomes = evaluate_profile_rules(profile.rules, data)
    for outcome in outcomes:
        match = re.search(r"(\d+)", outcome.rule_id)
        rule_num = int(match.group(1)) if match else None
        if outcome.passed:
            if rule_num is not None:
                rules_passed.append(rule_num)
            continue

        message = f"[{outcome.rule_id}] {outcome.message}"
        if outcome.severity == "warning":
            warnings.append(message)
        else:
            errors.append(message)
            if rule_num is not None:
                rules_failed.append(rule_num)

    return errors, warnings, sorted(set(rules_passed)), sorted(set(rules_failed))
