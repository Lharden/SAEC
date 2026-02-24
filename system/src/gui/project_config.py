"""Project-specific configuration management."""

from __future__ import annotations

from pathlib import Path


BLANK_PROJECT_DEFAULTS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "LLM_PROVIDERS_FILE": "config/providers.yaml",
    "ANTHROPIC_MODEL": "",
    "OPENAI_MODEL": "",
    "OLLAMA_ENABLED": "true",
    "OLLAMA_BASE_URL": "http://localhost:11434/v1",
    "PRIMARY_PROVIDER": "ollama",
    "PROVIDER_EXTRACT": "auto",
    "PROVIDER_REPAIR": "auto",
    "PROVIDER_QUOTES": "auto",
    "PROVIDER_CASCADE_API": "auto",
    "USE_TWO_PASS": "true",
    "OLLAMA_MODEL_CLOUD": "qwen3-coder-next:cloud",
    "OLLAMA_MODEL_CLOUD_FALLBACK": "glm-5:cloud",
    "OLLAMA_MODEL_CODER": "qwen3-coder-next:cloud",
    "OLLAMA_MODEL_VISION": "qwen3-vl:8b",
    "OLLAMA_EXTRACTION_MODEL": "qwen3-coder-next:cloud",
    "OLLAMA_REPAIR_MODEL": "glm-4.7:cloud",
    "OLLAMA_OCR_MODEL": "glm-ocr:latest",
    "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text-v2-moe:latest",
    "OLLAMA_RERANKER_MODEL": "qllama/bge-reranker-v2-m3:q4_k_m",
}


class ProjectConfig:
    """Manages project-specific configuration stored as .env file."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.config_path = project_root / ".env"

    def exists(self) -> bool:
        return self.config_path.exists()

    def load(self) -> dict[str, str]:
        """Load project configuration from .env file."""
        if not self.config_path.exists():
            return {}
        values: dict[str, str] = {}
        try:
            for raw in self.config_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            return {}
        return values

    def save(self, values: dict[str, str]) -> None:
        """Save project configuration to .env file."""
        self.project_root.mkdir(parents=True, exist_ok=True)
        lines = ["# SAEC project configuration"]
        for key, value in values.items():
            lines.append(f"{key}={value}")
        self.config_path.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    def get_effective_values(self) -> dict[str, str]:
        """Return merged defaults + saved values (saved takes priority)."""
        result = dict(BLANK_PROJECT_DEFAULTS)
        result.update(self.load())
        return result


def get_blank_project_defaults() -> dict[str, str]:
    """Return a copy of the blank project defaults."""
    return dict(BLANK_PROJECT_DEFAULTS)
