"""Configuração central do SAEC-O&G."""

import csv
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
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
        self.GUIA_PROMPT = self.SYSTEM / "prompts" / "guia_v3_3_prompt.md"
        self.GUIA_FULL = self.PROJECT_ROOT / "Guia v3.3.md"

    def ensure_dirs(self):
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
            "claude-3-5-sonnet-20241022",
        )
    )
    OPENAI_MODEL: str = field(
        default_factory=lambda: _env_str("OPENAI_MODEL", "gpt-4o")
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

    def get_httpx_timeout(self):
        """Retorna um objeto httpx.Timeout com base na config."""
        try:
            import httpx
        except Exception:
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

        available = {
            "anthropic": has_anthropic,
            "openai": has_openai,
            "ollama": has_ollama,
        }
        if self.PRIMARY_PROVIDER not in available:
            errors.append(
                f"PRIMARY_PROVIDER inválido: {self.PRIMARY_PROVIDER}. Use anthropic, openai ou ollama."
            )
        elif not available[self.PRIMARY_PROVIDER]:
            errors.append(
                f"PRIMARY_PROVIDER={self.PRIMARY_PROVIDER} não está disponível com a configuração atual."
            )

        return errors

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
            "openai": status(self.OPENAI_API_KEY),
            "ollama": (
                f"{'ON' if self.OLLAMA_ENABLED else 'OFF'} "
                f"(cloud={self.OLLAMA_MODEL_CLOUD}, "
                f"coder={self.OLLAMA_MODEL_CODER}, "
                f"vision={self.OLLAMA_MODEL_VISION} @ {self.OLLAMA_BASE_URL})"
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
    if output_path.exists() and not overwrite:
        print(f"[INFO] Mapping já existe: {output_path}")
        print(f"[INFO] Use overwrite=True para regenerar")
        return output_path

    # Listar PDFs em ordem alfabética
    pdfs = sorted(articles_dir.glob("*.pdf"))

    if not pdfs:
        raise ValueError(f"Nenhum PDF encontrado em {articles_dir}")

    # Gerar mapeamento
    rows = []
    for i, pdf in enumerate(pdfs, start=1):
        rows.append(
            {
                "ArtigoID": f"ART_{i:03d}",
                "Arquivo": pdf.name,
                "Processado": "Não",
                "Status": "",
            }
        )

    # Salvar CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ArtigoID", "Arquivo", "Processado", "Status"],
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
    print("=== SAEC-O&G Config Test ===")
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
