"""Configuração central do SAEC."""

import csv
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from dotenv import load_dotenv


# Carregar .env do diretório system
def _detect_project_root() -> Path:
    """Detecta raiz do projeto em runtime normal e executável empacotado."""
    env_root = os.getenv("SAEC_PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            exe_dir,
            exe_dir.parent,
            exe_dir.parent.parent,
            Path.cwd().resolve(),
        ]
        for candidate in candidates:
            if (candidate / "system").exists() and (candidate / "Extraction").exists():
                return candidate
        return Path.cwd().resolve()

    return Path(__file__).resolve().parent.parent.parent


_PROJECT_ROOT = _detect_project_root()
_system_dir = _PROJECT_ROOT / "system"
if not _system_dir.exists():
    _system_dir = Path(__file__).resolve().parent.parent

_env_path = _system_dir / ".env"
if _env_path.exists():
    load_dotenv(
        _env_path, override=True
    )  # override=True para recarregar em kernels Jupyter
else:
    # Tentar carregar de .env.template se .env não existir
    load_dotenv(_system_dir / ".env.template", override=True)


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_bool(key: str, default: str) -> bool:
    return os.getenv(key, default).lower() == "true"


def _env_int(key: str, default: str) -> int:
    return int(os.getenv(key, default))


def _env_float(key: str, default: str) -> float:
    return float(os.getenv(key, default))


def _is_placeholder_api_key(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return True

    placeholder_markers = (
        "your-",
        "-here",
        "placeholder",
        "sua",
        "sk-ant-sua",
        "sk-sua",
    )
    return any(marker in normalized for marker in placeholder_markers)


@dataclass
class Paths:
    """Caminhos do projeto."""

    # Raiz do projeto (00 Dados RSL)
    PROJECT_ROOT: Path = field(default_factory=lambda: _PROJECT_ROOT)

    def __post_init__(self):
        # Pastas principais
        self.SYSTEM = self.PROJECT_ROOT / "system"
        if not self.SYSTEM.exists():
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                self.SYSTEM = Path(meipass).resolve()
        self.CONFIG = self.PROJECT_ROOT / "config"
        if not self.CONFIG.exists():
            self.CONFIG = self.SYSTEM / "config"

        # Nome do diretório de artigos (configurável via .env)
        articles_override = _env_str("SAEC_ARTICLES_PATH", "").strip()
        if articles_override:
            self.ARTICLES = Path(articles_override).expanduser().resolve()
        else:
            articles_dir_name = _env_str("ARTICLES_DIR", "02 T2")
            self.ARTICLES = (self.PROJECT_ROOT / articles_dir_name).resolve()

        extraction_override = _env_str("SAEC_EXTRACTION_PATH", "").strip()
        if extraction_override:
            self.EXTRACTION = Path(extraction_override).expanduser().resolve()
        else:
            self.EXTRACTION = (self.PROJECT_ROOT / "Extraction").resolve()

        # Outputs
        self.OUTPUTS = self.EXTRACTION / "outputs"
        self.WORK = self.OUTPUTS / "work"
        self.YAMLS = self.OUTPUTS / "yamls"
        self.CONSOLIDATED = self.OUTPUTS / "consolidated"

        # Arquivos importantes
        self.MAPPING_CSV = self.EXTRACTION / "mapping.csv"
        prompt_candidates = [
            self.CONFIG / "prompts" / "guia_v3_3_prompt.md",
            self.SYSTEM / "prompts" / "guia_v3_3_prompt.md",
        ]
        self.GUIA_PROMPT = next(
            (path for path in prompt_candidates if path.exists()),
            prompt_candidates[0],
        )
        universal_prompt_candidates = [
            self.CONFIG / "prompts" / "universal_profile_prompt.md",
            self.SYSTEM / "prompts" / "universal_profile_prompt.md",
        ]
        self.UNIVERSAL_PROFILE_PROMPT = next(
            (path for path in universal_prompt_candidates if path.exists()),
            universal_prompt_candidates[0],
        )
        self.PROFILES_ROOT = self.CONFIG / "profiles"
        self.GUIA_FULL = self.PROJECT_ROOT / "Guia v3.3.md"

    def ensure_dirs(self) -> None:
        """Cria diretórios se não existirem."""
        for path in [self.WORK, self.YAMLS, self.CONSOLIDATED]:
            path.mkdir(parents=True, exist_ok=True)

    def get_article_work_dir(self, artigo_id: str) -> Path:
        """Retorna diretório de trabalho para um artigo."""
        work_dir = self.WORK / artigo_id
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir


@dataclass
class LLMConfig:
    """Configuração dos LLMs."""

    # APIs (cloud)
    ANTHROPIC_API_KEY: str = field(
        default_factory=lambda: _env_str("ANTHROPIC_API_KEY", "")
    )
    OPENAI_API_KEY: str = field(default_factory=lambda: _env_str("OPENAI_API_KEY", ""))
    OPENAI_BASE_URL: str = field(
        default_factory=lambda: _env_str("OPENAI_BASE_URL", "")
    )

    # Ollama (local)
    OLLAMA_ENABLED: bool = field(
        default_factory=lambda: _env_bool("OLLAMA_ENABLED", "true")
    )
    OLLAMA_BASE_URL: str = field(
        default_factory=lambda: _env_str(
            "OLLAMA_BASE_URL",
            "http://localhost:11434/v1",
        )
    )

    # Modelos (cloud)
    ANTHROPIC_MODEL: str = field(
        default_factory=lambda: _env_str(
            "ANTHROPIC_MODEL",
            "",
        )
    )
    OPENAI_MODEL: str = field(
        default_factory=lambda: _env_str("OPENAI_MODEL", "")
    )

    # Modelos (Ollama)
    # Separar modelos por função para manter qualidade/custo:
    # - *_CLOUD: tarefas complexas via Ollama cloud proxy (sem usar VRAM)
    # - *_CODER: tarefas mecânicas locais (format/repair fallback)
    # - *_VISION: extração com imagens (multimodal local)
    OLLAMA_MODEL_CLOUD: str = field(
        default_factory=lambda: _env_str(
            "OLLAMA_MODEL_CLOUD",
            "glm-4.7:cloud",
        )
    )
    OLLAMA_MODEL_CLOUD_FALLBACK: str = field(
        default_factory=lambda: _env_str(
            "OLLAMA_MODEL_CLOUD_FALLBACK",
            "kimi-k2.5:cloud",
        )
    )
    OLLAMA_MODEL_CODER: str = field(
        default_factory=lambda: _env_str(
            "OLLAMA_MODEL_CODER",
            "qwen3-vl:8b",
        )
    )
    OLLAMA_MODEL_VISION: str = field(
        default_factory=lambda: _env_str(
            "OLLAMA_MODEL_VISION",
            "qwen3-vl:8b",
        )
    )

    # Estratégia
    USE_TWO_PASS: bool = field(
        default_factory=lambda: _env_bool("USE_TWO_PASS", "true")
    )
    PRIMARY_PROVIDER: str = field(
        default_factory=lambda: _env_str("PRIMARY_PROVIDER", "ollama")
    )
    PROVIDER_EXTRACT: str = field(
        default_factory=lambda: _env_str("PROVIDER_EXTRACT", "auto")
    )
    PROVIDER_REPAIR: str = field(
        default_factory=lambda: _env_str("PROVIDER_REPAIR", "auto")
    )
    PROVIDER_QUOTES: str = field(
        default_factory=lambda: _env_str("PROVIDER_QUOTES", "auto")
    )
    PROVIDER_CASCADE_API: str = field(
        default_factory=lambda: _env_str("PROVIDER_CASCADE_API", "auto")
    )

    # Limites
    MAX_REPAIR_ATTEMPTS: int = field(
        default_factory=lambda: _env_int("MAX_REPAIR_ATTEMPTS", "3")
    )

    # Timeouts (segundos)
    TIMEOUT_TOTAL: float = field(
        default_factory=lambda: _env_float("LLM_TIMEOUT_TOTAL", "180")
    )
    TIMEOUT_CONNECT: float = field(
        default_factory=lambda: _env_float("LLM_TIMEOUT_CONNECT", "15")
    )
    TIMEOUT_READ: float = field(
        default_factory=lambda: _env_float("LLM_TIMEOUT_READ", "165")
    )

    # Retry
    RETRY_MAX_RETRIES: int = field(
        default_factory=lambda: _env_int("LLM_RETRY_MAX_RETRIES", "3")
    )
    RETRY_BASE_DELAY: float = field(
        default_factory=lambda: _env_float("LLM_RETRY_BASE_DELAY", "1.0")
    )
    RETRY_MAX_DELAY: float = field(
        default_factory=lambda: _env_float("LLM_RETRY_MAX_DELAY", "30.0")
    )
    RETRY_JITTER: float = field(
        default_factory=lambda: _env_float("LLM_RETRY_JITTER", "0.25")
    )
    RETRY_MAX_ELAPSED: float = field(
        default_factory=lambda: _env_float("LLM_RETRY_MAX_ELAPSED", "120.0")
    )

    # Prompt caching
    PROMPT_CACHE_ENABLED: bool = field(
        default_factory=lambda: _env_bool("PROMPT_CACHE_ENABLED", "true")
    )
    PROMPT_CACHE_KEY: str = field(
        default_factory=lambda: _env_str("PROMPT_CACHE_KEY", "saec_guia_v3_3")
    )
    PROMPT_CACHE_RETENTION: str = field(
        default_factory=lambda: _env_str("PROMPT_CACHE_RETENTION", "in_memory")
    )  # OpenAI: in_memory | 24h
    ANTHROPIC_CACHE_TTL: str = field(
        default_factory=lambda: _env_str("ANTHROPIC_CACHE_TTL", "5m")
    )  # 5m | 1h
    PROMPT_MIN_TEXT_CHARS: int = field(
        default_factory=lambda: _env_int("PROMPT_MIN_TEXT_CHARS", "0")
    )  # 0 = desativado

    def get_httpx_timeout(self) -> Any:
        """Retorna um objeto httpx.Timeout com base na config."""
        try:
            import httpx
        except (ImportError, ModuleNotFoundError):
            return self.TIMEOUT_TOTAL

        return httpx.Timeout(
            timeout=self.TIMEOUT_TOTAL,
            connect=self.TIMEOUT_CONNECT,
            read=self.TIMEOUT_READ,
        )

    def validate(self) -> list[str]:
        """Valida configuração. Retorna lista de erros."""
        errors = []

        has_anthropic = not _is_placeholder_api_key(self.ANTHROPIC_API_KEY)
        has_openai = not _is_placeholder_api_key(self.OPENAI_API_KEY)
        has_ollama = bool(self.OLLAMA_ENABLED)

        if has_anthropic and not (self.ANTHROPIC_MODEL or "").strip():
            errors.append(
                "ANTHROPIC_MODEL obrigatório quando ANTHROPIC_API_KEY estiver configurada."
            )
        if has_openai and not (self.OPENAI_MODEL or "").strip():
            errors.append(
                "OPENAI_MODEL obrigatório quando OPENAI_API_KEY estiver configurada."
            )

        # Pelo menos um provider de extração precisa estar disponível.
        if not (has_ollama or has_openai or has_anthropic):
            errors.append(
                "Nenhum provider disponível: configure OLLAMA_ENABLED=true ou uma API key válida (OPENAI/ANTHROPIC)."
            )

        # Com two-pass ativo, é necessário ao menos um provider para repair.
        if self.USE_TWO_PASS and not (has_ollama or has_openai or has_anthropic):
            errors.append(
                "USE_TWO_PASS=true exige ao menos um provider configurado para repair (Ollama/OpenAI/Anthropic)."
            )

        provider_routes = {
            "PROVIDER_EXTRACT": self._provider_choice(self.PROVIDER_EXTRACT),
            "PROVIDER_REPAIR": self._provider_choice(self.PROVIDER_REPAIR),
            "PROVIDER_QUOTES": self._provider_choice(self.PROVIDER_QUOTES),
        }
        for key, value in provider_routes.items():
            if value not in {"auto", "anthropic", "openai", "ollama"}:
                errors.append(
                    f"{key} inválido: {value}. Use auto, anthropic, openai ou ollama."
                )

        cascade_choice = self._provider_choice(self.PROVIDER_CASCADE_API)
        if cascade_choice not in {"auto", "anthropic", "openai"}:
            errors.append(
                f"PROVIDER_CASCADE_API inválido: {cascade_choice}. Use auto, anthropic ou openai."
            )

        available = {
            "anthropic": has_anthropic,
            "openai": has_openai,
            "ollama": has_ollama,
        }
        primary_provider = self._provider_choice(self.PRIMARY_PROVIDER)
        if primary_provider not in available:
            errors.append(
                f"PRIMARY_PROVIDER inválido: {self.PRIMARY_PROVIDER}. Use anthropic, openai ou ollama."
            )
        else:
            needs_primary = (
                any(value == "auto" for value in provider_routes.values())
                or cascade_choice == "auto"
            )
            if needs_primary and not available[primary_provider]:
                errors.append(
                    f"PRIMARY_PROVIDER={self.PRIMARY_PROVIDER} não está disponível com a configuração atual."
                )

        return errors

    @staticmethod
    def _provider_choice(value: str) -> str:
        return (value or "auto").strip().lower()

    def get_masked_keys(self) -> dict:
        """Retorna status das chaves para exibição (sem expor fragmentos)."""

        def status(key: str) -> str:
            if not key or len(key.strip()) < 10:
                return "NÃO CONFIGURADA"
            if _is_placeholder_api_key(key):
                return "NÃO CONFIGURADA (placeholder)"
            return "CONFIGURADA [OK]"

        return {
            "anthropic": status(self.ANTHROPIC_API_KEY),
            "openai": (
                f"{status(self.OPENAI_API_KEY)}"
                + (
                    f" @ {self.OPENAI_BASE_URL.strip()}"
                    if self.OPENAI_BASE_URL.strip()
                    else ""
                )
            ),
            "ollama": (
                f"{'ON' if self.OLLAMA_ENABLED else 'OFF'} "
                f"(cloud={self.OLLAMA_MODEL_CLOUD}, "
                f"coder={self.OLLAMA_MODEL_CODER}, "
                f"vision={self.OLLAMA_MODEL_VISION} @ {self.OLLAMA_BASE_URL})"
            ),
            "routing": (
                f"extract={self._provider_choice(self.PROVIDER_EXTRACT)}, "
                f"repair={self._provider_choice(self.PROVIDER_REPAIR)}, "
                f"quotes={self._provider_choice(self.PROVIDER_QUOTES)}, "
                f"cascade_api={self._provider_choice(self.PROVIDER_CASCADE_API)}"
            ),
        }


@dataclass
class LocalProcessingConfig:
    """Configuração para processamento local (marker, surya, ollama)."""

    # Marker-PDF
    MARKER_ENABLED: bool = field(
        default_factory=lambda: _env_bool("MARKER_ENABLED", "true")
    )
    MARKER_BATCH_MULTIPLIER: int = field(
        default_factory=lambda: _env_int("MARKER_BATCH_MULTIPLIER", "2")
    )

    # Surya-OCR
    SURYA_ENABLED: bool = field(
        default_factory=lambda: _env_bool("SURYA_ENABLED", "true")
    )
    SURYA_DPI: int = field(default_factory=lambda: _env_int("SURYA_DPI", "300"))

    # RAG
    RAG_ENABLED: bool = field(default_factory=lambda: _env_bool("RAG_ENABLED", "true"))
    RAG_CHUNK_SIZE: int = field(
        default_factory=lambda: _env_int("RAG_CHUNK_SIZE", "1000")
    )
    RAG_CHUNK_OVERLAP: int = field(
        default_factory=lambda: _env_int("RAG_CHUNK_OVERLAP", "200")
    )
    RAG_TOP_K: int = field(default_factory=lambda: _env_int("RAG_TOP_K", "3"))
    RAG_MIN_CONTEXT_CHARS: int = field(
        default_factory=lambda: _env_int("RAG_MIN_CONTEXT_CHARS", "1200")
    )
    RAG_MIN_CONTEXT_RATIO: float = field(
        default_factory=lambda: _env_float("RAG_MIN_CONTEXT_RATIO", "0.15")
    )

    # Redução determinística de ruído (headers/footers repetidos)
    STRIP_REPEATED_LINES: bool = field(
        default_factory=lambda: _env_bool("STRIP_REPEATED_LINES", "true")
    )
    REPEAT_LINE_MIN_FRACTION: float = field(
        default_factory=lambda: _env_float("REPEAT_LINE_MIN_FRACTION", "0.5")
    )
    REPEAT_LINE_MAX_LEN: int = field(
        default_factory=lambda: _env_int("REPEAT_LINE_MAX_LEN", "80")
    )

    # Estratégia de cascata
    EXTRACTION_STRATEGY: str = field(
        default_factory=lambda: _env_str("EXTRACTION_STRATEGY", "local_first")
    )  # local_first | api_first | local_only | api_only

    LOCAL_CONFIDENCE_THRESHOLD: float = field(
        default_factory=lambda: _env_float("LOCAL_CONFIDENCE_THRESHOLD", "0.7")
    )
    USE_CASCADE: bool = field(default_factory=lambda: _env_bool("USE_CASCADE", "false"))

    # Modelos Ollama por tarefa (cloud-first para economia)
    OLLAMA_EXTRACTION_MODEL: str = field(
        default_factory=lambda: _env_str("OLLAMA_EXTRACTION_MODEL", "glm-4.7:cloud")
    )
    OLLAMA_REPAIR_MODEL: str = field(
        default_factory=lambda: _env_str("OLLAMA_REPAIR_MODEL", "glm-4.7:cloud")
    )
    OLLAMA_OCR_MODEL: str = field(
        default_factory=lambda: _env_str("OLLAMA_OCR_MODEL", "glm-ocr:latest")
    )
    OLLAMA_EMBEDDING_MODEL: str = field(
        default_factory=lambda: _env_str(
            "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text-v2-moe:latest"
        )
    )


@dataclass
class ExtractionConfig:
    """Configuração de extração."""

    # Sempre usar estratégia híbrida (texto quando possível + imagens só quando necessário)
    FORCE_HYBRID: bool = field(
        default_factory=lambda: _env_bool("FORCE_HYBRID", "true")
    )

    # DPI apenas para páginas que realmente viram imagem
    IMAGE_DPI: int = field(default_factory=lambda: _env_int("IMAGE_DPI", "300"))

    # Heurísticas de PDF (compatíveis com pdf_vision)
    PDF_HEADER_REGION: float = field(
        default_factory=lambda: _env_float("PDF_HEADER_REGION", "0.12")
    )
    PDF_FOOTER_REGION: float = field(
        default_factory=lambda: _env_float("PDF_FOOTER_REGION", "0.12")
    )
    PDF_MIN_IMAGE_AREA_RATIO: float = field(
        default_factory=lambda: _env_float("PDF_MIN_IMAGE_AREA_RATIO", "0.03")
    )
    PDF_REFERENCES_START_RATIO: float = field(
        default_factory=lambda: _env_float("PDF_REFERENCES_START_RATIO", "0.6")
    )
    PDF_REFERENCES_END_RATIO: float = field(
        default_factory=lambda: _env_float("PDF_REFERENCES_END_RATIO", "0.7")
    )
    PDF_REFERENCES_MIN_LINES: int = field(
        default_factory=lambda: _env_int("PDF_REFERENCES_MIN_LINES", "15")
    )
    PDF_REFERENCES_SCAN_LINES: int = field(
        default_factory=lambda: _env_int("PDF_REFERENCES_SCAN_LINES", "15")
    )

    # Quote matching tolerante (para OCR)
    QUOTE_MATCH_RATIO: float = field(
        default_factory=lambda: _env_float("QUOTE_MATCH_RATIO", "0.98")
    )

    MIN_QUOTES: int = 3
    MAX_QUOTES: int = 8


# ============================================================
# Funções de Mapping
# ============================================================


_MAPPING_FIELDS = ["ArtigoID", "Arquivo", "Processado", "Status"]


def _parse_article_sequence(artigo_id: str) -> int | None:
    match = re.match(r"^ART_(\d+)$", (artigo_id or "").strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _normalize_mapping_row(row: dict[str, str]) -> dict[str, str]:
    artigo_id = (row.get("ArtigoID", "") or "").strip()
    arquivo = (row.get("Arquivo", "") or "").strip()
    processado = (row.get("Processado", "Não") or "Não").strip() or "Não"
    status = (row.get("Status", "") or "").strip()
    return {
        "ArtigoID": artigo_id,
        "Arquivo": arquivo,
        "Processado": processado,
        "Status": status,
    }


def _read_existing_mapping_rows(mapping_path: Path) -> list[dict[str, str]]:
    if not mapping_path.exists():
        return []
    try:
        with open(mapping_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except (OSError, csv.Error):
        return []
    if not rows:
        return []
    return [_normalize_mapping_row(row) for row in rows]


def _mapping_is_current(
    existing_rows: list[dict[str, str]],
    *,
    pdf_names: list[str],
) -> bool:
    if not existing_rows:
        return False
    expected = set(pdf_names)
    valid_rows = [row for row in existing_rows if row["Arquivo"] and row["ArtigoID"]]
    if not valid_rows:
        return False
    mapped_names = {row["Arquivo"] for row in valid_rows}
    if mapped_names != expected:
        return False
    ids = [row["ArtigoID"] for row in valid_rows]
    if len(ids) != len(set(ids)):
        return False
    return True


def _sync_mapping_rows(
    existing_rows: list[dict[str, str]],
    *,
    pdf_names: list[str],
) -> list[dict[str, str]]:
    existing_by_file: dict[str, dict[str, str]] = {}
    used_ids: set[str] = set()
    max_sequence = 0

    for raw in existing_rows:
        row = _normalize_mapping_row(raw)
        arquivo = row["Arquivo"]
        artigo_id = row["ArtigoID"]
        if not arquivo or not artigo_id or arquivo in existing_by_file:
            continue
        existing_by_file[arquivo] = row
        used_ids.add(artigo_id)
        sequence = _parse_article_sequence(artigo_id)
        if sequence is not None:
            max_sequence = max(max_sequence, sequence)

    next_sequence = max_sequence + 1
    synced: list[dict[str, str]] = []
    for pdf_name in pdf_names:
        existing = existing_by_file.get(pdf_name)
        if existing is not None:
            synced.append(existing)
            continue
        while True:
            artigo_id = f"ART_{next_sequence:03d}"
            next_sequence += 1
            if artigo_id not in used_ids:
                break
        used_ids.add(artigo_id)
        synced.append(
            {
                "ArtigoID": artigo_id,
                "Arquivo": pdf_name,
                "Processado": "Não",
                "Status": "",
            }
        )
    return synced


def generate_mapping_csv(
    articles_dir: Path,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """
    Gera mapping.csv com ArtigoID para cada PDF.

    Args:
        articles_dir: Pasta com PDFs
        output_path: Caminho do CSV de saída
        overwrite: Se True, sobrescreve existente

    Returns:
        Path do CSV gerado
    """
    # Listar PDFs em ordem alfabética
    pdfs = sorted(articles_dir.glob("*.pdf"))

    if not pdfs:
        raise ValueError(f"Nenhum PDF encontrado em {articles_dir}")

    pdf_names = [pdf.name for pdf in pdfs]
    existing_rows = _read_existing_mapping_rows(output_path)

    if output_path.exists() and not overwrite:
        if _mapping_is_current(existing_rows, pdf_names=pdf_names):
            print(f"[INFO] Mapping já existe: {output_path}")
            print("[INFO] Mapping está sincronizado com a pasta de artigos")
            return output_path

        if existing_rows:
            print(f"[WARN] Mapping desatualizado: {output_path}")
            print("[INFO] Sincronizando mapping com PDFs atuais...")
        else:
            print(f"[WARN] Mapping vazio ou inválido: {output_path}")
            print("[INFO] Regenerando mapping...")

        rows = _sync_mapping_rows(existing_rows, pdf_names=pdf_names)

        try:
            backup_path = output_path.with_suffix(output_path.suffix + ".bak")
            backup_path.write_bytes(output_path.read_bytes())
            print(f"[INFO] Backup do mapping anterior: {backup_path}")
        except OSError:
            pass
    else:
        # Regeneração completa (overwrite=True) ou primeiro mapping.
        rows = _sync_mapping_rows([], pdf_names=pdf_names)

    # Salvar CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=_MAPPING_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Mapping gerado: {output_path}")
    print(f"[OK] {len(rows)} artigos mapeados")
    return output_path


def load_mapping(mapping_path: Path) -> list[dict[str, str]]:
    """Carrega mapping.csv como lista de dicts."""
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping não encontrado: {mapping_path}")

    with open(mapping_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def update_mapping_status(
    mapping_path: Path,
    artigo_id: str,
    processado: bool,
    status: str,
) -> None:
    """Atualiza status de um artigo no mapping."""
    rows = load_mapping(mapping_path)

    updated = False
    for row in rows:
        if row["ArtigoID"] == artigo_id:
            row["Processado"] = "Sim" if processado else "Não"
            row["Status"] = status
            updated = True
            break

    if not updated:
        print(f"[WARN] ArtigoID não encontrado no mapping: {artigo_id}")
        return

    with open(mapping_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"],
        )
        writer.writeheader()
        writer.writerows(rows)


def get_pending_articles(mapping_path: Path) -> list[dict[str, str]]:
    """Retorna lista de artigos não processados."""
    mapping = load_mapping(mapping_path)
    return [m for m in mapping if m["Processado"] != "Sim"]


def get_article_by_id(mapping_path: Path, artigo_id: str) -> dict[str, str] | None:
    """Busca artigo pelo ID."""
    mapping = load_mapping(mapping_path)
    for m in mapping:
        if m["ArtigoID"] == artigo_id:
            return m
    return None


# ============================================================
# Instâncias Globais
# ============================================================

paths = Paths()
llm_config = LLMConfig()
extraction_config = ExtractionConfig()
local_config = LocalProcessingConfig()


# ============================================================
# Teste de importação
# ============================================================

if __name__ == "__main__":
    print("=== SAEC Config Test ===")
    print(f"Project root: {paths.PROJECT_ROOT}")
    print(f"Articles dir: {paths.ARTICLES}")
    print(f"Articles exist: {paths.ARTICLES.exists()}")
    print(f"Outputs dir: {paths.OUTPUTS}")

    print("\nLLM Config:")
    print(f"  Two-pass: {llm_config.USE_TWO_PASS}")
    print(f"  Primary: {llm_config.PRIMARY_PROVIDER}")
    print(f"  Keys: {llm_config.get_masked_keys()}")

    errors = llm_config.validate()
    if errors:
        print(f"\nErros de configuração:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"\n[OK] Configuração válida")

