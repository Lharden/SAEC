"""
Adapter para surya-ocr.

OCR de alta qualidade para:
- PDFs escaneados
- Páginas com texto em imagens
- Documentos multilíngue
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from PIL import Image
from PIL.Image import Image as PILImage

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
class BoundingBox:
    """Bounding box de texto detectado."""
    x1: float
    y1: float
    x2: float
    y2: float
    text: str
    confidence: float


@dataclass
class OCRResult:
    """Resultado de OCR de uma imagem."""
    text: str
    confidence: float
    bboxes: list[BoundingBox]
    languages_detected: list[str]
    processing_time_ms: float
    width: int = 0
    height: int = 0


@dataclass
class PageOCRResult:
    """Resultado de OCR de uma página de PDF."""
    page_number: int
    ocr_result: OCRResult
    dpi: int


@dataclass
class SuryaConfig:
    """Configuração do surya-ocr."""
    languages: list[str] = field(default_factory=lambda: ["en"])
    detection_batch_size: int = 4
    recognition_batch_size: int = 4
    use_gpu: bool = True


# ============================================================
# Funções de Verificação
# ============================================================

def is_surya_available() -> bool:
    """Verifica se surya-ocr está instalado."""
    try:
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor
        return True
    except ImportError:
        return False


def is_gpu_available() -> bool:
    """Verifica se GPU está disponível para surya."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def get_surya_info() -> dict:
    """Retorna informações sobre a instalação do surya."""
    info = {
        "available": is_surya_available(),
        "gpu_available": is_gpu_available(),
        "supported_languages": [],
    }

    if info["available"]:
        # Surya suporta muitos idiomas
        info["supported_languages"] = ["en", "pt", "es", "fr", "de", "it", "zh", "ja", "ko"]

    return info


# ============================================================
# Funções de OCR
# ============================================================

# Cache global para modelos (evita recarregar)
_surya_predictors = None


def _get_predictors():
    """Carrega ou retorna predictors em cache."""
    global _surya_predictors
    if _surya_predictors is None:
        logger.info("Carregando modelos surya-ocr...")
        from surya.recognition import RecognitionPredictor
        from surya.detection import DetectionPredictor

        _surya_predictors = {
            "detection": DetectionPredictor(),
            "recognition": RecognitionPredictor(),
        }
        logger.info("Modelos surya-ocr carregados")

    return _surya_predictors


def ocr_image(
    image: Union[Path, PILImage],
    *,
    languages: list[str] | None = None,
    config: SuryaConfig | None = None,
) -> OCRResult:
    """
    Executa OCR em uma imagem.

    Args:
        image: Caminho da imagem ou PIL Image
        languages: Idiomas alvo (padrão: ["en"])
        config: Configuração opcional

    Returns:
        OCRResult com texto e bounding boxes

    Raises:
        IngestError: Se OCR falhar
    """
    if not is_surya_available():
        raise IngestError("surya-ocr não está instalado")

    config = config or SuryaConfig()
    languages = languages or config.languages

    try:
        start_time = time.time()

        # Carregar imagem se necessário
        if isinstance(image, Path):
            if not image.exists():
                raise IngestError(f"Imagem não encontrada: {image}")
            img: PILImage = Image.open(image)
        else:
            img = image

        # Converter para RGB se necessário
        if img.mode != "RGB":
            img = img.convert("RGB")

        width, height = img.size

        # Carregar predictors
        predictors = _get_predictors()

        # Executar detecção
        det_results = predictors["detection"]([img])

        # Executar reconhecimento
        rec_results = predictors["recognition"]([img], det_results)

        # Processar resultado
        if not rec_results or len(rec_results) == 0:
            return OCRResult(
                text="",
                confidence=0.0,
                bboxes=[],
                languages_detected=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                width=width,
                height=height,
            )

        result = rec_results[0]

        # Extrair texto e bboxes
        bboxes = []
        full_text_parts = []
        total_confidence = 0.0

        for line in result.text_lines:
            text = line.text
            conf = getattr(line, 'confidence', 1.0)
            bbox = getattr(line, 'bbox', [0, 0, 0, 0])

            full_text_parts.append(text)
            total_confidence += conf

            bboxes.append(BoundingBox(
                x1=bbox[0] if len(bbox) > 0 else 0,
                y1=bbox[1] if len(bbox) > 1 else 0,
                x2=bbox[2] if len(bbox) > 2 else 0,
                y2=bbox[3] if len(bbox) > 3 else 0,
                text=text,
                confidence=conf,
            ))

        full_text = "\n".join(full_text_parts)
        avg_confidence = total_confidence / len(bboxes) if bboxes else 0.0

        elapsed_ms = (time.time() - start_time) * 1000

        return OCRResult(
            text=full_text,
            confidence=avg_confidence,
            bboxes=bboxes,
            languages_detected=languages,
            processing_time_ms=elapsed_ms,
            width=width,
            height=height,
        )

    except Exception as e:
        logger.error(f"Erro no OCR surya: {e}")
        raise IngestError(f"Surya OCR failed: {e}")


def ocr_pdf_pages(
    pdf_path: Path,
    page_numbers: list[int] | None = None,
    *,
    dpi: int = 300,
    languages: list[str] | None = None,
) -> list[PageOCRResult]:
    """
    Executa OCR em páginas específicas de um PDF.

    Args:
        pdf_path: Caminho do PDF
        page_numbers: Páginas para OCR (1-indexed, None = todas)
        dpi: Resolução para renderização
        languages: Idiomas alvo

    Returns:
        Lista de PageOCRResult

    Raises:
        IngestError: Se OCR falhar
    """
    if not pdf_path.exists():
        raise IngestError(f"PDF não encontrado: {pdf_path}")

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Determinar páginas a processar
        if page_numbers is None:
            page_numbers = list(range(1, total_pages + 1))
        else:
            # Validar números de página
            page_numbers = [p for p in page_numbers if 1 <= p <= total_pages]

        results = []

        for page_num in page_numbers:
            logger.info(f"OCR página {page_num}/{total_pages}...")

            # Renderizar página como imagem
            page = doc[page_num - 1]  # 0-indexed
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # Converter para PIL Image
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            # Executar OCR
            ocr_result = ocr_image(img, languages=languages)

            results.append(PageOCRResult(
                page_number=page_num,
                ocr_result=ocr_result,
                dpi=dpi,
            ))

        doc.close()
        return results

    except Exception as e:
        logger.error(f"Erro no OCR de PDF: {e}")
        raise IngestError(f"PDF OCR failed: {e}")


def ocr_pdf_full(
    pdf_path: Path,
    *,
    dpi: int = 300,
    languages: list[str] | None = None,
) -> str:
    """
    Executa OCR completo em um PDF.

    Args:
        pdf_path: Caminho do PDF
        dpi: Resolução
        languages: Idiomas

    Returns:
        Texto completo extraído
    """
    results = ocr_pdf_pages(pdf_path, page_numbers=None, dpi=dpi, languages=languages)

    full_text_parts = []
    for result in results:
        full_text_parts.append(f"--- Página {result.page_number} ---")
        full_text_parts.append(result.ocr_result.text)
        full_text_parts.append("")

    return "\n".join(full_text_parts)


# ============================================================
# Funções de Análise
# ============================================================

def detect_scanned_pdf(
    pdf_path: Path,
    sample_pages: int = 3,
) -> dict:
    """
    Detecta se PDF é escaneado (baseado em imagens).

    Args:
        pdf_path: Caminho do PDF
        sample_pages: Número de páginas para amostrar

    Returns:
        Dict com análise
    """
    try:
        import fitz

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_to_check = min(sample_pages, total_pages)

        total_text_chars = 0
        total_images = 0

        for i in range(pages_to_check):
            page = doc[i]
            text = _normalize_text_payload(page.get_text())
            images = page.get_images()

            total_text_chars += len(text.strip())
            total_images += len(images)

        doc.close()

        avg_chars = total_text_chars / pages_to_check if pages_to_check > 0 else 0
        avg_images = total_images / pages_to_check if pages_to_check > 0 else 0

        # Heurística: poucos caracteres + imagens = provável scan
        is_scanned = avg_chars < 100 and avg_images > 0

        return {
            "total_pages": total_pages,
            "sampled_pages": pages_to_check,
            "avg_chars_per_page": avg_chars,
            "avg_images_per_page": avg_images,
            "is_likely_scanned": is_scanned,
            "confidence": 0.9 if (avg_chars < 50 or avg_chars > 500) else 0.6,
        }

    except Exception as e:
        logger.warning(f"Erro ao detectar PDF escaneado: {e}")
        return {
            "total_pages": 0,
            "is_likely_scanned": False,
            "confidence": 0.0,
            "error": str(e),
        }


def estimate_ocr_time(
    pdf_path: Path,
    dpi: int = 300,
) -> dict:
    """
    Estima tempo de OCR para um PDF.

    Args:
        pdf_path: Caminho do PDF
        dpi: Resolução planejada

    Returns:
        Dict com estimativas
    """
    try:
        import fitz

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()

        # Estimativas baseadas em benchmarks típicos
        # GPU: ~2-5 segundos por página em 300 DPI
        # CPU: ~10-20 segundos por página
        gpu = is_gpu_available()

        time_per_page = 3 if gpu else 15  # segundos
        total_time = total_pages * time_per_page

        return {
            "total_pages": total_pages,
            "dpi": dpi,
            "gpu_available": gpu,
            "estimated_time_per_page_sec": time_per_page,
            "estimated_total_time_sec": total_time,
            "estimated_total_time_min": total_time / 60,
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    print("=== Surya Adapter Test ===\n")

    info = get_surya_info()
    print(f"Disponível: {info['available']}")
    print(f"GPU: {info['gpu_available']}")
    print(f"Idiomas suportados: {info['supported_languages']}")

    if info['available']:
        import sys
        if len(sys.argv) > 1:
            path = Path(sys.argv[1])
            if path.exists():
                if path.suffix.lower() == ".pdf":
                    print(f"\nAnalisando PDF {path.name}...")
                    analysis = detect_scanned_pdf(path)
                    print(f"  Páginas: {analysis.get('total_pages', 0)}")
                    print(f"  Provável scan: {analysis.get('is_likely_scanned', False)}")

                    estimate = estimate_ocr_time(path)
                    print(f"  Tempo estimado: {estimate.get('estimated_total_time_min', 0):.1f} min")
                else:
                    print(f"\nExecutando OCR em {path.name}...")
                    result = ocr_image(path)
                    print(f"  Texto extraído: {len(result.text)} chars")
                    print(f"  Confiança: {result.confidence:.2f}")
                    print(f"  Tempo: {result.processing_time_ms:.0f}ms")
