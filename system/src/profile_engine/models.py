"""Declarative profile models used by the profile engine."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


CURRENT_PROFILE_SCHEMA_VERSION = "1.0"
SUPPORTED_PROFILE_SCHEMA_VERSIONS = frozenset({CURRENT_PROFILE_SCHEMA_VERSION})


_ALLOWED_FIELD_TYPES = {
    "string",
    "text",
    "int",
    "float",
    "bool",
    "enum",
    "list",
    "object",
}
_ALLOWED_RULE_SEVERITY = {"error", "warning"}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ProfileMeta:
    profile_id: str
    version: str
    name: str
    domain: str = ""
    framework: str = "CUSTOM"
    language: str = "pt-BR"
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileMeta":
        return cls(
            profile_id=str(data.get("profile_id", "")).strip(),
            version=str(data.get("version", "")).strip(),
            name=str(data.get("name", "")).strip(),
            domain=str(data.get("domain", "")).strip(),
            framework=str(data.get("framework", "CUSTOM")).strip() or "CUSTOM",
            language=str(data.get("language", "pt-BR")).strip() or "pt-BR",
            description=str(data.get("description", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "name": self.name,
            "domain": self.domain,
            "framework": self.framework,
            "language": self.language,
            "description": self.description,
        }


@dataclass(frozen=True)
class TopicConfig:
    min_topics: int = 1
    max_topics: int = 50
    weighting_mode: str = "optional"
    default_weight: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TopicConfig":
        return cls(
            min_topics=max(_to_int(data.get("min_topics", 1), 1), 0),
            max_topics=max(_to_int(data.get("max_topics", 50), 50), 1),
            weighting_mode=str(data.get("weighting_mode", "optional")).strip()
            or "optional",
            default_weight=float(data.get("default_weight", 1.0) or 1.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_topics": self.min_topics,
            "max_topics": self.max_topics,
            "weighting_mode": self.weighting_mode,
            "default_weight": self.default_weight,
        }


@dataclass(frozen=True)
class ProfileField:
    field_id: str
    label: str
    section: str
    field_type: str
    required: bool = True
    multiple: bool = False
    min_length: int = 0
    max_length: int = 0
    allowed_values: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    confidence_field: str | None = None
    extraction_hints: tuple[str, ...] = field(default_factory=tuple)
    regex_patterns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileField":
        allowed = data.get("allowed_values", [])
        aliases = data.get("aliases", [])
        return cls(
            field_id=str(data.get("id", "")).strip(),
            label=str(data.get("label", "")).strip() or str(data.get("id", "")).strip(),
            section=str(data.get("section", "custom")).strip() or "custom",
            field_type=str(data.get("type", "string")).strip().lower() or "string",
            required=_to_bool(data.get("required", True), True),
            multiple=_to_bool(data.get("multiple", False), False),
            min_length=max(_to_int(data.get("min_length", 0), 0), 0),
            max_length=max(_to_int(data.get("max_length", 0), 0), 0),
            allowed_values=tuple(str(v).strip() for v in allowed if str(v).strip())
            if isinstance(allowed, list)
            else tuple(),
            aliases=tuple(str(v).strip() for v in aliases if str(v).strip())
            if isinstance(aliases, list)
            else tuple(),
            description=str(data.get("description", "")).strip(),
            confidence_field=(
                str(data.get("confidence_field", "")).strip() or None
            ),
            extraction_hints=tuple(
                str(v).strip()
                for v in data.get("extraction_hints", [])
                if str(v).strip()
            )
            if isinstance(data.get("extraction_hints", []), list)
            else tuple(),
            regex_patterns=tuple(
                str(v).strip()
                for v in data.get("regex_patterns", [])
                if str(v).strip()
            )
            if isinstance(data.get("regex_patterns", []), list)
            else tuple(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.field_id,
            "label": self.label,
            "section": self.section,
            "type": self.field_type,
            "required": self.required,
            "multiple": self.multiple,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "allowed_values": list(self.allowed_values),
            "aliases": list(self.aliases),
            "description": self.description,
            "confidence_field": self.confidence_field,
            "extraction_hints": list(self.extraction_hints),
            "regex_patterns": list(self.regex_patterns),
        }


@dataclass(frozen=True)
class ProfileRule:
    rule_id: str
    severity: str
    when: str
    assert_expr: str
    message: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileRule":
        return cls(
            rule_id=str(data.get("id", "")).strip(),
            severity=str(data.get("severity", "error")).strip().lower() or "error",
            when=str(data.get("when", "True")).strip() or "True",
            assert_expr=str(data.get("assert", "True")).strip() or "True",
            message=str(data.get("message", "Rule failed")).strip() or "Rule failed",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.rule_id,
            "severity": self.severity,
            "when": self.when,
            "assert": self.assert_expr,
            "message": self.message,
        }


@dataclass(frozen=True)
class QuoteSchema:
    id_pattern: str = r"^Q\d{3}$"
    required_fields: tuple[str, ...] = ("QuoteID", "TipoQuote", "Trecho", "Página")
    trecho_min_length: int = 10

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuoteSchema":
        required_fields_raw = data.get("required_fields", cls.required_fields)
        required_fields: tuple[str, ...]
        if isinstance(required_fields_raw, list):
            required_fields = tuple(
                str(v).strip() for v in required_fields_raw if str(v).strip()
            )
        else:
            required_fields = cls.required_fields

        return cls(
            id_pattern=str(data.get("id_pattern", cls.id_pattern)).strip()
            or cls.id_pattern,
            required_fields=required_fields or cls.required_fields,
            trecho_min_length=max(
                _to_int(data.get("trecho_min_length", cls.trecho_min_length), 10), 1
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id_pattern": self.id_pattern,
            "required_fields": list(self.required_fields),
            "trecho_min_length": self.trecho_min_length,
        }


@dataclass(frozen=True)
class QuotePolicy:
    enabled: bool = True
    min_quotes: int = 3
    max_quotes: int = 8
    required_types: tuple[str, ...] = field(default_factory=tuple)
    allowed_types: tuple[str, ...] = field(default_factory=lambda: ("Outro",))
    quote_schema: QuoteSchema = field(default_factory=QuoteSchema)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuotePolicy":
        required_types = data.get("required_types", [])
        allowed_types = data.get("allowed_types", [])
        quote_schema_raw = data.get("quote_schema", {})
        if not isinstance(quote_schema_raw, dict):
            quote_schema_raw = {}
        return cls(
            enabled=_to_bool(data.get("enabled", True), True),
            min_quotes=max(_to_int(data.get("min_quotes", 3), 3), 0),
            max_quotes=max(_to_int(data.get("max_quotes", 8), 8), 0),
            required_types=tuple(
                str(v).strip() for v in required_types if str(v).strip()
            )
            if isinstance(required_types, list)
            else tuple(),
            allowed_types=tuple(
                str(v).strip() for v in allowed_types if str(v).strip()
            )
            if isinstance(allowed_types, list)
            else tuple(),
            quote_schema=QuoteSchema.from_dict(quote_schema_raw),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "min_quotes": self.min_quotes,
            "max_quotes": self.max_quotes,
            "required_types": list(self.required_types),
            "allowed_types": list(self.allowed_types),
            "quote_schema": self.quote_schema.to_dict(),
        }


@dataclass(frozen=True)
class OutputContract:
    output_format: str = "yaml"
    enforce_field_names: bool = True
    include_sections: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutputContract":
        return cls(
            output_format=str(data.get("format", "yaml")).strip().lower() or "yaml",
            enforce_field_names=_to_bool(data.get("enforce_field_names", True), True),
            include_sections=_to_bool(data.get("include_sections", True), True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.output_format,
            "enforce_field_names": self.enforce_field_names,
            "include_sections": self.include_sections,
        }


@dataclass(frozen=True)
class PromptContract:
    return_only_output: bool = True
    include_self_review: bool = True
    instructions: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptContract":
        instructions = data.get("instructions", [])
        if not isinstance(instructions, list):
            instructions = []
        return cls(
            return_only_output=_to_bool(data.get("return_only_output", True), True),
            include_self_review=_to_bool(data.get("include_self_review", True), True),
            instructions=tuple(str(v).strip() for v in instructions if str(v).strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "return_only_output": self.return_only_output,
            "include_self_review": self.include_self_review,
            "instructions": list(self.instructions),
        }


@dataclass(frozen=True)
class ProfileSpec:
    schema_version: str
    meta: ProfileMeta
    topics: TopicConfig
    fields: tuple[ProfileField, ...]
    rules: tuple[ProfileRule, ...]
    quotes_policy: QuotePolicy
    output: OutputContract
    prompt_contract: PromptContract
    tests_required: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileSpec":
        profile = data.get("profile", data)
        if not isinstance(profile, dict):
            profile = {}
        schema_version = str(
            data.get("schema_version", profile.get("schema_version", ""))
        ).strip() or CURRENT_PROFILE_SCHEMA_VERSION
        meta_raw = profile.get("meta", {})
        topics_raw = profile.get("topics", {})
        fields_raw = profile.get("fields", [])
        rules_raw = profile.get("rules", [])
        quotes_raw = profile.get("quotes_policy", {})
        output_raw = profile.get("output", {})
        prompt_raw = profile.get("prompt_contract", {})
        tests_raw = profile.get("tests", {})

        if not isinstance(meta_raw, dict):
            meta_raw = {}
        if not isinstance(topics_raw, dict):
            topics_raw = {}
        if not isinstance(quotes_raw, dict):
            quotes_raw = {}
        if not isinstance(output_raw, dict):
            output_raw = {}
        if not isinstance(prompt_raw, dict):
            prompt_raw = {}
        if not isinstance(tests_raw, dict):
            tests_raw = {}

        fields: list[ProfileField] = []
        if isinstance(fields_raw, list):
            for item in fields_raw:
                if isinstance(item, dict):
                    fields.append(ProfileField.from_dict(item))

        rules: list[ProfileRule] = []
        if isinstance(rules_raw, list):
            for item in rules_raw:
                if isinstance(item, dict):
                    rules.append(ProfileRule.from_dict(item))

        tests_required_raw = tests_raw.get("required", [])
        tests_required: tuple[str, ...]
        if isinstance(tests_required_raw, list):
            tests_required = tuple(
                str(v).strip() for v in tests_required_raw if str(v).strip()
            )
        else:
            tests_required = tuple()

        return cls(
            schema_version=schema_version,
            meta=ProfileMeta.from_dict(meta_raw),
            topics=TopicConfig.from_dict(topics_raw),
            fields=tuple(fields),
            rules=tuple(rules),
            quotes_policy=QuotePolicy.from_dict(quotes_raw),
            output=OutputContract.from_dict(output_raw),
            prompt_contract=PromptContract.from_dict(prompt_raw),
            tests_required=tests_required,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile": {
                "meta": self.meta.to_dict(),
                "topics": self.topics.to_dict(),
                "fields": [field.to_dict() for field in self.fields],
                "rules": [rule.to_dict() for rule in self.rules],
                "quotes_policy": self.quotes_policy.to_dict(),
                "output": self.output.to_dict(),
                "prompt_contract": self.prompt_contract.to_dict(),
                "tests": {"required": list(self.tests_required)},
            }
        }

    def field_by_id(self, field_id: str) -> ProfileField | None:
        needle = (field_id or "").strip()
        if not needle:
            return None
        for field in self.fields:
            if field.field_id == needle:
                return field
            if needle in field.aliases:
                return field
        return None

    def validate_structure(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version not in SUPPORTED_PROFILE_SCHEMA_VERSIONS:
            errors.append(
                "schema_version is not supported "
                f"(got '{self.schema_version}', expected one of: "
                f"{', '.join(sorted(SUPPORTED_PROFILE_SCHEMA_VERSIONS))})"
            )
        if not self.meta.profile_id:
            errors.append("profile.meta.profile_id is required")
        if not self.meta.version:
            errors.append("profile.meta.version is required")
        if not self.meta.name:
            errors.append("profile.meta.name is required")

        if self.topics.max_topics < self.topics.min_topics:
            errors.append("profile.topics.max_topics must be >= min_topics")

        if not self.fields:
            errors.append("profile.fields must contain at least one field")
        if self.field_by_id("ArtigoID") is None:
            errors.append(
                "profile.fields must include 'ArtigoID' (required for pipeline mapping)"
            )

        seen_fields: set[str] = set()
        for field in self.fields:
            if not field.field_id:
                errors.append("profile.fields[*].id is required")
                continue
            if field.field_id in seen_fields:
                errors.append(f"duplicate field id: {field.field_id}")
            seen_fields.add(field.field_id)

            if field.field_type not in _ALLOWED_FIELD_TYPES:
                errors.append(
                    f"field '{field.field_id}' has invalid type '{field.field_type}'"
                )
            if (
                field.field_type == "enum"
                and not field.allowed_values
                and field.required
            ):
                errors.append(
                    f"field '{field.field_id}' is enum and requires allowed_values"
                )
            if field.max_length and field.max_length < field.min_length:
                errors.append(
                    f"field '{field.field_id}' has max_length < min_length"
                )
            for pattern in field.regex_patterns:
                try:
                    re.compile(pattern)
                except re.error:
                    errors.append(
                        f"field '{field.field_id}' has invalid regex pattern '{pattern}'"
                    )

        seen_rules: set[str] = set()
        for rule in self.rules:
            if not rule.rule_id:
                errors.append("profile.rules[*].id is required")
                continue
            if rule.rule_id in seen_rules:
                errors.append(f"duplicate rule id: {rule.rule_id}")
            seen_rules.add(rule.rule_id)
            if rule.severity not in _ALLOWED_RULE_SEVERITY:
                errors.append(
                    f"rule '{rule.rule_id}' has invalid severity '{rule.severity}'"
                )
            if not rule.assert_expr:
                errors.append(f"rule '{rule.rule_id}' requires assert expression")

        if self.quotes_policy.max_quotes < self.quotes_policy.min_quotes:
            errors.append("quotes_policy.max_quotes must be >= min_quotes")
        if self.output.output_format not in {"yaml", "json"}:
            errors.append("output.format must be 'yaml' or 'json'")

        return errors
