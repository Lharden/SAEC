"""Project-scoped profile version management."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

import yaml

from .loader import ProfileLoadError, load_profile_spec
from .models import CURRENT_PROFILE_SCHEMA_VERSION, ProfileSpec
from .xlsx_profiles import load_profile_spec_from_xlsx, write_profile_template_xlsx


PROFILE_FILE_NAME = "profile.yaml"
PROMPT_FILE_NAME = "extract_prompt.md"
PROFILE_ACTIVE_FILE = "profile_active.json"
RUN_AUDIT_DIR_NAME = "run_audit"


@dataclass(frozen=True)
class ActiveProfileRef:
    profile_id: str
    version: str
    schema_version: str
    profile_path: Path
    prompt_path: Path | None
    source: str
    updated_at: str


@dataclass(frozen=True)
class RunProfileSnapshot:
    run_id: str
    root_dir: Path
    profile_yaml_path: Path
    prompt_path: Path | None
    metadata_path: Path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def bundled_profiles_root() -> Path:
    return (_repo_root() / "config" / "profiles").resolve()


def bundled_profile_dir(profile_id: str) -> Path:
    clean = (profile_id or "").strip()
    return (bundled_profiles_root() / clean).resolve()


def list_bundled_profiles() -> list[str]:
    root = bundled_profiles_root()
    if not root.exists():
        return []
    items: list[str] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if (entry / PROFILE_FILE_NAME).exists():
            items.append(entry.name)
    return sorted(items)


def _bundled_profile_files(profile_id: str) -> tuple[Path, Path | None]:
    profile_dir = bundled_profile_dir(profile_id)
    profile_path = profile_dir / PROFILE_FILE_NAME
    prompt_candidates = [
        profile_dir / PROMPT_FILE_NAME,
        profile_dir / "prompts" / "extract.md",
        profile_dir / "prompts" / PROMPT_FILE_NAME,
    ]
    prompt_path = next((p for p in prompt_candidates if p.exists()), None)
    if not profile_path.exists():
        raise FileNotFoundError(f"Bundled profile not found: {profile_path}")
    return profile_path, prompt_path


def project_profile_root(project_root: Path) -> Path:
    return project_root.resolve() / "config" / "profiles"


def active_profile_file(project_root: Path) -> Path:
    return project_root.resolve() / "config" / PROFILE_ACTIVE_FILE


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _normalize_version(version: str) -> str:
    clean = (version or "").strip()
    return clean or "1.0.0"


def _ensure_unique_version(profile_dir: Path, version: str) -> str:
    normalized = _normalize_version(version)
    candidate = normalized
    suffix = 1
    while (profile_dir / candidate).exists():
        candidate = f"{normalized}-r{suffix}"
        suffix += 1
    return candidate


def build_universal_profile_prompt(spec: ProfileSpec) -> str:
    """Build one universal extraction prompt from the active profile contract."""
    framework = (spec.meta.framework or "CUSTOM").strip()
    lines: list[str] = [
        f"# Universal Extraction Prompt ({framework})",
        "",
        "Objetivo:",
        "Extrair dados do artigo e retornar SOMENTE YAML valido conforme o perfil ativo.",
        "",
        "Regras gerais obrigatorias:",
        "- Retorne apenas YAML, sem texto antes/depois.",
        "- Use apenas campos declarados no perfil ativo.",
        "- Nao invente valores sem evidencia no texto/imagens do artigo.",
        "- Mantenha nomes de campos exatamente como definidos no perfil.",
        "- Preserve consistencia semantica entre campos relacionados.",
        "- Quando faltar evidencia explicita, use NR ou vazio conforme o contrato do campo.",
        "- Quando houver quotes, use trechos literais e com pagina/secao quando aplicavel.",
        "",
        "Campos do perfil ativo:",
    ]

    for field in spec.fields:
        required = "obrigatorio" if field.required else "opcional"
        descriptor = f"- {field.field_id} ({field.field_type}, {required})"
        details: list[str] = []
        if field.allowed_values:
            details.append("valores: " + ", ".join(field.allowed_values))
        if field.regex_patterns:
            details.append("regex: " + "; ".join(field.regex_patterns))
        if field.description:
            details.append("descricao: " + field.description)
        if details:
            descriptor += " | " + " | ".join(details)
        lines.append(descriptor)

    if spec.rules:
        lines.extend(
            [
                "",
                "Regras declarativas do perfil (obrigatorias):",
            ]
        )
        for rule in spec.rules:
            lines.append(f"- {rule.rule_id}: {rule.message}")

    if spec.quotes_policy.enabled:
        lines.extend(
            [
                "",
                "Politica de quotes:",
                f"- Quantidade: {spec.quotes_policy.min_quotes} a {spec.quotes_policy.max_quotes}",
                "- Campos por quote: "
                + ", ".join(spec.quotes_policy.quote_schema.required_fields),
                f"- Padrao de QuoteID: {spec.quotes_policy.quote_schema.id_pattern}",
            ]
        )
        if spec.quotes_policy.required_types:
            lines.append(
                "- Tipos recomendados: " + ", ".join(spec.quotes_policy.required_types)
            )

    if spec.prompt_contract.instructions:
        lines.extend(["", "Instrucoes adicionais do perfil:"])
        for instruction in spec.prompt_contract.instructions:
            lines.append(f"- {instruction}")

    lines.extend(
        [
            "",
            "Checklist final antes de responder:",
            "- YAML valido e completo.",
            "- Sem campos fora do perfil.",
            "- Regras do perfil respeitadas.",
            "- Sem alucinacoes.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_profile_files(
    *,
    target_dir: Path,
    spec: ProfileSpec,
    prompt_text: str | None,
) -> tuple[Path, Path | None]:
    target_dir.mkdir(parents=True, exist_ok=True)
    profile_path = target_dir / PROFILE_FILE_NAME
    profile_path.write_text(
        yaml.safe_dump(
            spec.to_dict(),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    prompt_path: Path | None = None
    resolved_prompt_text = (prompt_text or "").strip()
    if not resolved_prompt_text:
        resolved_prompt_text = build_universal_profile_prompt(spec)
    if resolved_prompt_text:
        prompt_path = target_dir / PROMPT_FILE_NAME
        prompt_path.write_text(resolved_prompt_text.rstrip() + "\n", encoding="utf-8")
    return profile_path, prompt_path


def _update_project_manifest_profile(
    project_root: Path, *, profile_id: str, version: str, schema_version: str
) -> None:
    manifest_path = project_root.resolve() / "project.json"
    if not manifest_path.exists():
        return
    payload = _read_json(manifest_path)
    payload["active_profile_id"] = profile_id
    payload["active_profile_version"] = version
    payload["active_profile_schema_version"] = schema_version
    payload["profile_updated_at"] = _utc_now()
    _write_json(manifest_path, payload)


def _activate_ref(
    project_root: Path,
    *,
    profile_id: str,
    version: str,
    schema_version: str,
    profile_path: Path,
    prompt_path: Path | None,
    source: str,
) -> ActiveProfileRef:
    ref_payload = {
        "profile_id": profile_id,
        "version": version,
        "schema_version": schema_version,
        "profile_path": str(profile_path.resolve()),
        "prompt_path": str(prompt_path.resolve()) if prompt_path else "",
        "source": source,
        "updated_at": _utc_now(),
    }
    _write_json(active_profile_file(project_root), ref_payload)
    _update_project_manifest_profile(
        project_root,
        profile_id=profile_id,
        version=version,
        schema_version=schema_version,
    )
    return ActiveProfileRef(
        profile_id=profile_id,
        version=version,
        schema_version=schema_version,
        profile_path=profile_path.resolve(),
        prompt_path=prompt_path.resolve() if prompt_path else None,
        source=source,
        updated_at=ref_payload["updated_at"],
    )


def save_profile_version(
    project_root: Path,
    *,
    spec: ProfileSpec,
    prompt_text: str | None = None,
    activate: bool = True,
    source: str = "gui",
) -> ActiveProfileRef:
    """Save one profile version under project/config/profiles."""
    root = project_root.resolve()
    profile_dir = project_profile_root(root) / spec.meta.profile_id
    version = _ensure_unique_version(profile_dir, spec.meta.version)

    if version != spec.meta.version:
        # Keep stored metadata coherent when we generate a revision suffix.
        profile_payload = spec.to_dict()
        profile_payload["profile"]["meta"]["version"] = version
        spec = ProfileSpec.from_dict(profile_payload)

    target_dir = profile_dir / version
    profile_path, prompt_path = _write_profile_files(
        target_dir=target_dir,
        spec=spec,
        prompt_text=prompt_text,
    )

    if activate:
        return _activate_ref(
            root,
            profile_id=spec.meta.profile_id,
            version=spec.meta.version,
            schema_version=spec.schema_version,
            profile_path=profile_path,
            prompt_path=prompt_path,
            source=source,
        )
    return ActiveProfileRef(
        profile_id=spec.meta.profile_id,
        version=spec.meta.version,
        schema_version=spec.schema_version,
        profile_path=profile_path,
        prompt_path=prompt_path,
        source=source,
        updated_at=_utc_now(),
    )


def bootstrap_profile(
    project_root: Path, *, profile_id: str = "cimo_v3_3", activate: bool = True
) -> ActiveProfileRef:
    """Copy one bundled profile into the project and optionally activate it."""
    bundled_profile, bundled_prompt = _bundled_profile_files(profile_id)
    spec = load_profile_spec(bundled_profile)
    prompt_text = None
    if bundled_prompt and bundled_prompt.exists():
        prompt_text = bundled_prompt.read_text(encoding="utf-8")

    return save_profile_version(
        project_root,
        spec=spec,
        prompt_text=prompt_text,
        activate=activate,
        source=f"bundled:{profile_id}",
    )


def import_profile_yaml(
    project_root: Path,
    *,
    yaml_path: Path,
    prompt_path: Path | None = None,
    activate: bool = True,
) -> ActiveProfileRef:
    """Import profile declaration from YAML and store as project version."""
    source_yaml = Path(yaml_path).resolve()
    spec = load_profile_spec(source_yaml)
    prompt_text: str | None = None
    if prompt_path is not None and Path(prompt_path).exists():
        prompt_text = Path(prompt_path).read_text(encoding="utf-8")

    return save_profile_version(
        project_root,
        spec=spec,
        prompt_text=prompt_text,
        activate=activate,
        source="yaml_import",
    )


def import_profile_xlsx(
    project_root: Path,
    *,
    xlsx_path: Path,
    prompt_path: Path | None = None,
    activate: bool = True,
) -> ActiveProfileRef:
    """Import one profile from XLSX template and store as project version."""
    source_xlsx = Path(xlsx_path).resolve()
    result = load_profile_spec_from_xlsx(source_xlsx)
    prompt_text = result.prompt_text
    if prompt_path is not None and Path(prompt_path).exists():
        prompt_text = Path(prompt_path).read_text(encoding="utf-8")

    return save_profile_version(
        project_root,
        spec=result.spec,
        prompt_text=prompt_text,
        activate=activate,
        source="xlsx_import",
    )


def export_profile_template_xlsx(destination: Path) -> Path:
    """Export official XLSX template for profile configuration."""
    return write_profile_template_xlsx(destination)


def has_active_profile(project_root: Path) -> bool:
    ref = get_active_profile_ref(project_root)
    return ref is not None


def get_active_profile_ref(project_root: Path) -> ActiveProfileRef | None:
    payload = _read_json(active_profile_file(project_root))
    profile_id = str(payload.get("profile_id", "")).strip()
    version = str(payload.get("version", "")).strip()
    schema_version = str(payload.get("schema_version", "")).strip()
    profile_path_raw = str(payload.get("profile_path", "")).strip()
    prompt_path_raw = str(payload.get("prompt_path", "")).strip()
    source = str(payload.get("source", "")).strip() or "unknown"
    updated_at = str(payload.get("updated_at", "")).strip()

    if not profile_id or not version or not profile_path_raw:
        return None
    profile_path = Path(profile_path_raw)
    if not profile_path.exists():
        return None
    if not schema_version:
        try:
            schema_version = load_profile_spec(profile_path).schema_version
        except ProfileLoadError:
            schema_version = CURRENT_PROFILE_SCHEMA_VERSION

    prompt_path: Path | None = None
    if prompt_path_raw:
        candidate = Path(prompt_path_raw)
        if candidate.exists():
            prompt_path = candidate

    return ActiveProfileRef(
        profile_id=profile_id,
        version=version,
        schema_version=schema_version,
        profile_path=profile_path.resolve(),
        prompt_path=prompt_path.resolve() if prompt_path else None,
        source=source,
        updated_at=updated_at,
    )


def load_active_profile_spec(project_root: Path) -> tuple[ProfileSpec, ActiveProfileRef]:
    ref = get_active_profile_ref(project_root)
    if ref is None:
        raise ProfileLoadError(
            f"No active profile configured for project: {project_root}"
        )
    spec = load_profile_spec(ref.profile_path)
    return spec, ref


def resolve_profile_prompt_path(project_root: Path, fallback: Path | None = None) -> Path:
    """Resolve prompt path from active project profile."""
    ref = get_active_profile_ref(project_root)
    if ref and ref.prompt_path and ref.prompt_path.exists():
        return ref.prompt_path
    if fallback is not None:
        return fallback
    raise FileNotFoundError(
        f"No extract prompt configured for project profile in {project_root}"
    )


def resolve_runtime_project_root(default: Path | None = None) -> Path | None:
    raw = os.getenv("SAEC_EXTRACTION_PATH", "").strip()
    if raw:
        candidate = Path(raw).expanduser().resolve()
        if candidate.exists() and (candidate / "project.json").exists():
            return candidate
    if default is not None:
        resolved = default.resolve()
        if (resolved / "project.json").exists():
            return resolved
    return None


def is_default_cimo_profile(project_root: Path | None) -> bool:
    if project_root is None:
        return True
    ref = get_active_profile_ref(project_root)
    if ref is None:
        return True
    return ref.profile_id.strip().lower() == "cimo_v3_3"


def require_project_profile(project_root: Path) -> tuple[bool, str]:
    """Check if project has a valid active profile configured."""
    root = project_root.resolve()
    manifest = root / "project.json"
    if not manifest.exists():
        # Non-project folders (legacy scripts/tests) keep old behavior.
        return True, ""

    ref = get_active_profile_ref(root)
    if ref is None:
        return (
            False,
            "Project profile is not configured. Configure profile in GUI or import YAML before running.",
        )
    try:
        load_profile_spec(ref.profile_path)
    except ProfileLoadError as exc:
        return (
            False,
            f"Active profile is invalid: {exc}",
        )
    return True, ""


def clone_active_profile_to_file(project_root: Path, destination: Path) -> Path:
    """Export current active profile YAML to destination path."""
    spec, _ref = load_active_profile_spec(project_root)
    target = destination.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(spec.to_dict(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def _safe_filename_component(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "unknown"
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in raw)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("._") or "unknown"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_active_profile_for_run(
    project_root: Path,
    *,
    output_root: Path,
    run_id: str,
    command: str,
    force: bool = False,
    dry_run: bool = False,
) -> RunProfileSnapshot:
    """Write immutable snapshot of active profile under outputs for audit/reproducibility."""
    spec, ref = load_active_profile_spec(project_root)

    run_clean = _safe_filename_component(run_id)
    audit_root = output_root.resolve() / RUN_AUDIT_DIR_NAME / run_clean
    audit_root.mkdir(parents=True, exist_ok=True)

    profile_name = _safe_filename_component(spec.meta.profile_id)
    profile_version = _safe_filename_component(spec.meta.version)
    profile_yaml_path = audit_root / f"profile_{profile_name}_{profile_version}.yaml"
    yaml_text = yaml.safe_dump(spec.to_dict(), allow_unicode=True, sort_keys=False)
    profile_yaml_path.write_text(yaml_text, encoding="utf-8")
    profile_sha256 = _sha256_bytes(yaml_text.encode("utf-8"))

    prompt_snapshot_path: Path | None = None
    prompt_sha256 = ""
    if ref.prompt_path and ref.prompt_path.exists():
        prompt_snapshot_path = audit_root / PROMPT_FILE_NAME
        prompt_text = ref.prompt_path.read_text(encoding="utf-8", errors="replace")
        prompt_snapshot_path.write_text(prompt_text.rstrip() + "\n", encoding="utf-8")
        prompt_sha256 = _sha256_bytes(prompt_text.encode("utf-8"))

    metadata = {
        "run_id": run_clean,
        "created_at": _utc_now(),
        "command": command,
        "force": bool(force),
        "dry_run": bool(dry_run),
        "project_root": str(project_root.resolve()),
        "active_profile": {
            "profile_id": ref.profile_id,
            "version": ref.version,
            "schema_version": spec.schema_version,
            "source": ref.source,
            "updated_at": ref.updated_at,
            "origin_profile_path": str(ref.profile_path),
            "origin_prompt_path": str(ref.prompt_path) if ref.prompt_path else "",
        },
        "snapshot": {
            "root_dir": str(audit_root),
            "profile_yaml_path": str(profile_yaml_path),
            "profile_sha256": profile_sha256,
            "prompt_path": str(prompt_snapshot_path) if prompt_snapshot_path else "",
            "prompt_sha256": prompt_sha256,
        },
    }
    metadata_path = audit_root / "profile_snapshot.json"
    _write_json(metadata_path, metadata)

    return RunProfileSnapshot(
        run_id=run_clean,
        root_dir=audit_root,
        profile_yaml_path=profile_yaml_path,
        prompt_path=prompt_snapshot_path,
        metadata_path=metadata_path,
    )


def remove_profile_versions(project_root: Path, *, profile_id: str) -> None:
    """Utility for tests and maintenance."""
    target = project_profile_root(project_root) / profile_id
    if target.exists():
        shutil.rmtree(target)

