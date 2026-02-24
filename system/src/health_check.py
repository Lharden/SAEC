"""Runtime diagnostics and health checks for the desktop app."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
from typing import Literal
from urllib.error import URLError
from urllib.request import urlopen
import yaml


HealthStatus = Literal["OK", "WARN", "FAIL"]


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    status: HealthStatus
    details: str


def _ok(name: str, details: str) -> HealthCheckResult:
    return HealthCheckResult(name=name, status="OK", details=details)


def _warn(name: str, details: str) -> HealthCheckResult:
    return HealthCheckResult(name=name, status="WARN", details=details)


def _fail(name: str, details: str) -> HealthCheckResult:
    return HealthCheckResult(name=name, status="FAIL", details=details)


def _parse_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_python_runtime() -> HealthCheckResult:
    return _ok("Python runtime", f"Python {sys.version.split()[0]}")


def check_disk_space(target: Path, *, min_free_gb: float = 1.0) -> HealthCheckResult:
    usage = shutil.disk_usage(target)
    free_gb = usage.free / (1024**3)
    if free_gb < min_free_gb:
        return _warn(
            "Disk space",
            f"Low free space: {free_gb:.2f} GB (recommended >= {min_free_gb:.2f} GB)",
        )
    return _ok("Disk space", f"Free space: {free_gb:.2f} GB")


def check_api_keys(env_path: Path) -> HealthCheckResult:
    values = _parse_env_file(env_path)
    providers_file_raw = values.get("LLM_PROVIDERS_FILE", "").strip()
    if providers_file_raw:
        providers_file = Path(providers_file_raw).expanduser()
        if not providers_file.is_absolute():
            providers_file = (env_path.parent.parent / providers_file).resolve()
        if providers_file.exists():
            try:
                payload = yaml.safe_load(providers_file.read_text(encoding="utf-8")) or {}
                providers = payload.get("providers", {}) if isinstance(payload, dict) else {}
                configured: list[str] = []
                if isinstance(providers, dict):
                    for provider_id, spec in providers.items():
                        if not isinstance(spec, dict):
                            continue
                        enabled = str(spec.get("enabled", True)).lower() not in {
                            "0",
                            "false",
                            "no",
                            "off",
                        }
                        if not enabled:
                            continue
                        model = str(spec.get("model", "")).strip()
                        if not model:
                            continue
                        key_literal = str(spec.get("api_key", "")).strip()
                        key_env = str(spec.get("api_key_env", "")).strip()
                        if (
                            key_literal
                            or key_env
                            or str(spec.get("kind", "")).strip().lower() == "ollama"
                        ):
                            configured.append(str(provider_id))
                if configured:
                    return _ok(
                        "API keys",
                        "Providers YAML ativos: " + ", ".join(configured),
                    )
            except (OSError, yaml.YAMLError, ValueError):
                pass

    anthropic = bool(values.get("ANTHROPIC_API_KEY", "").strip())
    openai = bool(values.get("OPENAI_API_KEY", "").strip())
    extract_route = values.get("PROVIDER_EXTRACT", "auto").strip() or "auto"
    repair_route = values.get("PROVIDER_REPAIR", "auto").strip() or "auto"
    quotes_route = values.get("PROVIDER_QUOTES", "auto").strip() or "auto"
    cascade_route = values.get("PROVIDER_CASCADE_API", "auto").strip() or "auto"
    routing = (
        " | Routing: "
        f"extract={extract_route}, "
        f"repair={repair_route}, "
        f"quotes={quotes_route}, "
        f"cascade_api={cascade_route}"
    )
    if anthropic or openai:
        keys = []
        if anthropic:
            keys.append("Anthropic")
        if openai:
            base_url = values.get("OPENAI_BASE_URL", "").strip()
            if base_url:
                keys.append(f"OpenAI-compatible ({base_url})")
            else:
                keys.append("OpenAI-compatible")
        return _ok("API keys", "Configured: " + ", ".join(keys) + routing)
    return _warn("API keys", f"No API keys configured in {env_path.name}" + routing)


def check_python_packages(required: list[str] | None = None) -> HealthCheckResult:
    modules = required or ["yaml", "pandas", "openpyxl", "dotenv"]
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        return _fail("Python packages", "Missing: " + ", ".join(sorted(missing)))
    return _ok("Python packages", "All critical packages available")


def check_ollama_connectivity(base_url: str) -> HealthCheckResult:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[: -len("/v1")]
    url = normalized + "/api/tags"
    try:
        with urlopen(url, timeout=2.5) as response:
            if response.status != 200:
                return _warn("Ollama", f"Unexpected HTTP status {response.status}")
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except URLError as exc:
        return _warn("Ollama", f"Unavailable at {url}: {exc}")
    except Exception as exc:
        return _warn("Ollama", f"Unexpected error querying {url}: {exc}")

    models = payload.get("models", []) if isinstance(payload, dict) else []
    if not isinstance(models, list):
        models = []
    model_names: list[str] = []
    for model in models[:5]:
        if isinstance(model, dict):
            name = str(model.get("name", "")).strip()
            if name:
                model_names.append(name)
    if model_names:
        details = "Connected. Models: " + ", ".join(model_names)
    else:
        details = "Connected. No models reported."
    return _ok("Ollama", details)


def run_health_checks(
    *,
    workspace_root: Path | None,
    system_root: Path,
    ollama_url: str = "http://localhost:11434",
) -> list[HealthCheckResult]:
    checks: list[HealthCheckResult] = [check_python_runtime()]

    disk_target = workspace_root or system_root
    checks.append(check_disk_space(disk_target))
    checks.append(check_python_packages())

    env_path = system_root / ".env"
    checks.append(check_api_keys(env_path))
    checks.append(check_ollama_connectivity(ollama_url))

    return checks
