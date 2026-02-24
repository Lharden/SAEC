"""
Adapter para marker-pdf.

Conversão de PDF para Markdown estruturado com:
- Preservação de estrutura (headers, listas, tabelas)
- Extração de imagens/figuras
- OCR integrado para páginas escaneadas
- Suporte a GPU para aceleração
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from ..exceptions import IngestError
except ImportError:  # pragma: no cover - standalone usage
    from exceptions import IngestError

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes
# ============================================================


def _normalize_text_payload(payload: object) -> str:
    """Normaliza payload textual dinâmico para string."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "\n".join(str(item) for item in payload)
    if isinstance(payload, dict):
        return "\n".join(f"{key}: {value}" for key, value in payload.items())
    return str(payload)


@dataclass
class MarkerPage:
    """Informações de uma página processada pelo marker."""
    page_number: int
    text: str
    has_images: bool = False
    has_tables: bool = False
    word_count: int = 0


@dataclass
class MarkerResult:
    """Resultado da conversão marker-pdf."""
    markdown: str
    metadata: dict[str, Any]
    pages: list[MarkerPage]
    images: list[Path]
    tables: list[str]
    processing_time_ms: float
    source_path: Path
    output_dir: Path
    success: bool = True
    error: str | None = None

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def total_words(self) -> int:
        return sum(p.word_count for p in self.pages)

    @property
    def pages_with_images(self) -> int:
        return sum(1 for p in self.pages if p.has_images)


@dataclass
class MarkerConfig:
    """Configuração do marker-pdf."""
    batch_multiplier: int = 2
    extract_images: bool = True
    ocr_all_pages: bool = False
    languages: list[str] = field(default_factory=lambda: ["en"])
    max_pages: int | None = None
    use_gpu: bool = True
    output_format: str = "markdown"


# ============================================================
# Funções de Verificação
# ============================================================

def is_marker_available() -> bool:
    """Verifica se marker-pdf está instalado e funcional."""
    try:
        import marker.converters.pdf as marker_pdf
        return marker_pdf is not None
    except ImportError:
        return False


def is_gpu_available() -> bool:
    """Verifica se GPU está disponível para marker."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def get_marker_info() -> dict:
    """Retorna informações sobre a instalação do marker."""
    info: dict[str, object] = {
        "available": is_marker_available(),
        "gpu_available": is_gpu_available(),
        "version": None,
    }

    if info["available"]:
        try:
            import marker
            version = getattr(marker, "__version__", None)
            info["version"] = str(version) if version is not None else "unknown"
        except (AttributeError, ImportError, TypeError):
            pass

    return info


# ============================================================
# Funções de Conversão
# ============================================================

def _run_marker_conversion(pdf_path: Path) -> Any:
    """Executa conversão marker e retorna objeto renderizado."""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    gpu_available = is_gpu_available()
    logger.info(
        "Loading marker-pdf models (GPU: %s)",
        gpu_available,
        extra={"action": "convert", "gpu": gpu_available},
    )
    model_dict = create_model_dict()
    converter = PdfConverter(artifact_dict=model_dict)
    logger.info("Converting %s", pdf_path.name, extra={"action": "convert", "file": pdf_path.name})
    return converter(str(pdf_path))


def _build_marker_pages(markdown_content: str) -> list[MarkerPage]:
    """Converte markdown extraído em métricas por página."""
    page_texts = (
        markdown_content.split("\n\n---\n\n")
        if "\n\n---\n\n" in markdown_content
        else [markdown_content]
    )
    pages: list[MarkerPage] = []
    for page_num, text in enumerate(page_texts, start=1):
        pages.append(
            MarkerPage(
                page_number=page_num,
                text=text,
                has_images="![" in text,
                has_tables="|" in text and "---" in text,
                word_count=len(text.split()),
            )
        )
    return pages


def _save_markdown_output(markdown_content: str, pdf_path: Path, output_dir: Path) -> Path:
    md_path = output_dir / f"{pdf_path.stem}.md"
    md_path.write_text(markdown_content, encoding="utf-8")
    return md_path


def _collect_rendered_images(rendered: object, output_dir: Path) -> list[Path]:
    images: list[Path] = []
    rendered_images = getattr(rendered, "images", None)
    if not rendered_images:
        return images
    images_dir = output_dir / "images"
    images_dir.mkdir(exist_ok=True)
    for img_name, img_data in rendered_images.items():
        img_path = images_dir / img_name
        if isinstance(img_data, bytes):
            img_path.write_bytes(img_data)
        images.append(img_path)
    return images


def _collect_rendered_tables(rendered: object) -> list[str]:
    tables = getattr(rendered, "tables", None)
    if isinstance(tables, list):
        return tables
    return []


def convert_pdf_to_markdown(
    pdf_path: Path,
    output_dir: Path,
    *,
    config: MarkerConfig | None = None,
) -> MarkerResult:
    """
    Converte PDF para Markdown usando marker-pdf.

    Args:
        pdf_path: Caminho do PDF de entrada
        output_dir: Diretório para saída
        config: Configuração opcional

    Returns:
        MarkerResult com markdown e metadados

    Raises:
        IngestError: Se conversão falhar
    """
    config = config or MarkerConfig()

    if not pdf_path.exists():
        raise IngestError(f"PDF não encontrado: {pdf_path}")

    if not is_marker_available():
        raise IngestError("marker-pdf não está instalado")

    try:
        start_time = time.time()

        output_dir.mkdir(parents=True, exist_ok=True)
        rendered = _run_marker_conversion(pdf_path)
        markdown_content = rendered.markdown
        metadata = rendered.metadata if hasattr(rendered, "metadata") else {}
        pages = _build_marker_pages(markdown_content)
        _save_markdown_output(markdown_content, pdf_path, output_dir)
        images = _collect_rendered_images(rendered, output_dir)
        tables = _collect_rendered_tables(rendered)

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            "Conversion done: %d pages, %d words, %.0fms",
            len(pages), sum(p.word_count for p in pages), elapsed_ms,
            extra={"action": "stats", "pages": len(pages), "time_ms": elapsed_ms},
        )

        return MarkerResult(
            markdown=markdown_content,
            metadata=metadata,
            pages=pages,
            images=images,
            tables=tables,
            processing_time_ms=elapsed_ms,
            source_path=pdf_path,
            output_dir=output_dir,
        )

    except Exception as e:  # Broad: PDF libraries raise diverse error types
        logger.error(
            "Marker-pdf conversion error: %s", e,
            extra={"action": "convert"},
        )
        raise IngestError(f"Marker conversion failed: {e}")


def convert_pdf_simple(
    pdf_path: Path,
    output_dir: Path,
) -> str:
    """
    Conversão simplificada - retorna apenas o markdown.

    Args:
        pdf_path: Caminho do PDF
        output_dir: Diretório de saída

    Returns:
        String com conteúdo markdown
    """
    result = convert_pdf_to_markdown(pdf_path, output_dir)
    return result.markdown


def extract_text_only(
    pdf_path: Path,
) -> str:
    """
    Extrai apenas texto do PDF (sem salvar arquivos).

    Útil para processamento rápido onde não precisa de imagens.

    Args:
        pdf_path: Caminho do PDF

    Returns:
        Texto extraído
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        result = convert_pdf_to_markdown(pdf_path, Path(tmpdir))
        return result.markdown


# ============================================================
# Funções de Análise
# ============================================================

def analyze_pdf_quality(pdf_path: Path) -> dict:
    """
    Analisa qualidade do PDF para decidir estratégia de extração.

    Args:
        pdf_path: Caminho do PDF

    Returns:
        Dict com métricas de qualidade
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Amostrar algumas páginas
        sample_pages = min(5, total_pages)
        text_chars = 0
        image_count = 0

        for i in range(sample_pages):
            page = doc[i]
            text_chars += len(_normalize_text_payload(page.get_text()))
            image_count += len(page.get_images())

        doc.close()

        avg_chars_per_page = text_chars / sample_pages if sample_pages > 0 else 0
        is_likely_scanned = avg_chars_per_page < 100  # Poucas letras = provavelmente scan

        return {
            "total_pages": total_pages,
            "avg_chars_per_page": avg_chars_per_page,
            "sample_image_count": image_count,
            "is_likely_scanned": is_likely_scanned,
            "recommended_strategy": "ocr" if is_likely_scanned else "text",
        }

    except Exception as e:  # Broad: PDF libraries raise diverse error types
        logger.warning(
            "PDF analysis error: %s", e,
            extra={"action": "analyze"},
        )
        return {
            "total_pages": 0,
            "avg_chars_per_page": 0,
            "sample_image_count": 0,
            "is_likely_scanned": False,
            "recommended_strategy": "text",
            "error": str(e),
        }


def compare_with_pymupdf(pdf_path: Path) -> dict:
    """
    Compara extração marker-pdf com PyMuPDF.

    Útil para decidir qual método usar.

    Args:
        pdf_path: Caminho do PDF

    Returns:
        Dict com comparação
    """
    import tempfile

    import fitz

    # Extrair com PyMuPDF
    doc = fitz.open(pdf_path)
    pymupdf_text_parts: list[str] = []
    for page in doc:
        pymupdf_text_parts.append(_normalize_text_payload(page.get_text()))
    doc.close()
    pymupdf_text = "\n".join(pymupdf_text_parts)
    pymupdf_words = len(pymupdf_text.split())

    # Extrair com marker
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = convert_pdf_to_markdown(pdf_path, Path(tmpdir))
            marker_words = result.total_words
            marker_time = result.processing_time_ms
        except Exception:  # Broad: PDF libraries raise diverse error types
            marker_words = 0
            marker_time = 0

    return {
        "pymupdf_words": pymupdf_words,
        "marker_words": marker_words,
        "marker_time_ms": marker_time,
        "word_ratio": marker_words / pymupdf_words if pymupdf_words > 0 else 0,
        "recommendation": "marker" if marker_words >= pymupdf_words * 0.9 else "pymupdf",
    }


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    print("=== Marker Adapter Test ===\n")

    info = get_marker_info()
    print(f"Disponível: {info['available']}")
    print(f"GPU: {info['gpu_available']}")
    print(f"Versão: {info['version']}")

    if info['available']:
        # Testar com um PDF se fornecido como argumento
        import sys
        if len(sys.argv) > 1:
            pdf_path = Path(sys.argv[1])
            if pdf_path.exists():
                print(f"\nAnalisando {pdf_path.name}...")
                quality = analyze_pdf_quality(pdf_path)
                print(f"  Páginas: {quality['total_pages']}")
                print(f"  Chars/página: {quality['avg_chars_per_page']:.0f}")
                print(f"  Provavelmente scan: {quality['is_likely_scanned']}")
                print(f"  Estratégia recomendada: {quality['recommended_strategy']}")
