"""Renderização de PDF como imagens para LLM com visão (estratégia híbrida)."""

import base64
import logging
import os
import re
from pathlib import Path
from typing import Any
import fitz  # PyMuPDF

# Configurar logger
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÕES DA ESTRATÉGIA HÍBRIDA
# =============================================================================
def _load_extraction_config():
    try:
        from .config import extraction_config as cfg
    except (ImportError, ModuleNotFoundError):  # pragma: no cover - standalone usage
        try:
            from config import extraction_config as cfg
        except (ImportError, ModuleNotFoundError):
            cfg = None
    return cfg


_cfg = _load_extraction_config()

# Regiões a ignorar para detecção de imagens (% da altura da página)
HEADER_REGION = getattr(_cfg, "PDF_HEADER_REGION", float(os.getenv("PDF_HEADER_REGION", "0.12")))
FOOTER_REGION = getattr(_cfg, "PDF_FOOTER_REGION", float(os.getenv("PDF_FOOTER_REGION", "0.12")))

# Tamanho mínimo de imagem para considerar relevante (% da área da página)
MIN_IMAGE_AREA_RATIO = getattr(_cfg, "PDF_MIN_IMAGE_AREA_RATIO", float(os.getenv("PDF_MIN_IMAGE_AREA_RATIO", "0.03")))

# Padrões para detectar início de referências
REFERENCES_PATTERNS = [
    r"^\s*References?\s*$",
    r"^\s*REFERENCES?\s*$",
    r"^\s*Bibliography\s*$",
    r"^\s*BIBLIOGRAPHY\s*$",
    r"^\s*Works?\s+Cited\s*$",
    r"^\s*Literature\s+Cited\s*$",
    r"^\s*Referências\s*$",
    r"^\s*REFERÊNCIAS\s*$",
]

# Títulos de seção de referências para busca no TOC
REFERENCES_TOC_KEYWORDS = [
    "references", "bibliography", "works cited",
    "literature cited", "referências", "referencias"
]


def _get_references_page_from_toc(doc) -> int | None:
    """
    Usa o Table of Contents (bookmarks) do PDF para encontrar a página de referências.

    Returns:
        Número da página onde começam as referências (1-indexed), ou None se não encontrar
    """
    try:
        toc = doc.get_toc()
        if not toc:
            return None

        for item in toc:
            # item = [level, title, page_number]
            level, title, page_num = item[0], item[1], item[2]
            title_lower = title.lower().strip()

            # Verificar se o título contém keywords de referências
            for keyword in REFERENCES_TOC_KEYWORDS:
                if keyword in title_lower:
                    return page_num  # Já é 1-indexed no PyMuPDF TOC

        return None
    except Exception:
        return None


def _find_references_start_in_text(text: str) -> int | None:
    """
    Encontra a posição (índice de caractere) onde as referências começam no texto.

    Returns:
        Índice do início da seção de referências, ou None se não encontrar
    """
    lines = text.split("\n")
    char_pos = 0

    for line in lines:
        line_stripped = line.strip()

        # Verificar se a linha é um título de referências
        for pattern in REFERENCES_PATTERNS:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                return char_pos

        char_pos += len(line) + 1  # +1 para o \n

    return None


# =============================================================================
# FUNÇÕES DE ANÁLISE DE PÁGINA
# =============================================================================

def _has_relevant_images(page) -> bool:
    """
    Verifica se a página tem imagens relevantes (não headers/footers/logos).

    Args:
        page: Página do PyMuPDF

    Returns:
        True se tem imagens de conteúdo relevantes
    """
    page_rect = page.rect
    page_height = page_rect.height
    page_width = page_rect.width
    page_area = page_height * page_width

    # Regiões de header e footer a ignorar
    header_limit = page_height * HEADER_REGION
    footer_limit = page_height * (1 - FOOTER_REGION)

    # Verificar imagens
    images = page.get_images(full=True)

    for img in images:
        try:
            # Obter posição da imagem na página
            img_rects = page.get_image_rects(img[0])
            if not img_rects:
                continue

            for rect in img_rects:
                # Verificar se está na região de conteúdo (não header/footer)
                img_center_y = (rect.y0 + rect.y1) / 2

                if img_center_y < header_limit or img_center_y > footer_limit:
                    continue  # Ignorar imagens em header/footer

                # Verificar tamanho da imagem
                img_area = rect.width * rect.height
                area_ratio = img_area / page_area

                if area_ratio >= MIN_IMAGE_AREA_RATIO:
                    return True  # Imagem relevante encontrada

        except Exception as e:
            logger.debug(f"Could not get image rect: {e}")
            continue

    # Verificar desenhos/gráficos
    drawings = page.get_drawings()
    if drawings:
        # Filtrar desenhos significativos (não linhas simples)
        significant_drawings = 0
        for d in drawings:
            if d.get("rect"):
                rect = d["rect"]
                # Ignorar header/footer
                center_y = (rect.y0 + rect.y1) / 2
                if header_limit <= center_y <= footer_limit:
                    area = (rect.x1 - rect.x0) * (rect.y1 - rect.y0)
                    if area / page_area >= MIN_IMAGE_AREA_RATIO:
                        significant_drawings += 1

        if significant_drawings >= 3:  # Múltiplos desenhos = provavelmente gráfico
            return True

    return False


def _is_references_page(page, page_num: int, total_pages: int) -> bool:
    """
    Detecta se a página é início de referências.
    Mais conservador: só detecta se encontrar título explícito.

    Args:
        page: Página do PyMuPDF
        page_num: Número da página (1-indexed)
        total_pages: Total de páginas do documento

    Returns:
        True se é início da seção de referências
    """
    # Referências geralmente estão no último 40% do documento
    # Se estamos antes de 60% do documento, não é referências
    references_start_ratio = getattr(_cfg, "PDF_REFERENCES_START_RATIO", 0.6)
    if page_num < total_pages * references_start_ratio:
        return False

    text = str(page.get_text())
    lines = text.split("\n")

    scan_lines = getattr(_cfg, "PDF_REFERENCES_SCAN_LINES", 15)
    for i, line in enumerate(lines[:scan_lines]):
        line_clean = line.strip()

        # Ignorar linhas muito curtas ou muito longas
        if len(line_clean) < 5 or len(line_clean) > 50:
            continue

        for pattern in REFERENCES_PATTERNS:
            if re.match(pattern, line_clean, re.IGNORECASE):
                # Verificar se é título isolado (não parte de sentença)
                # Título geralmente tem menos de 20 chars e está sozinho ou com número
                if len(line_clean) < 25:
                    return True

    # Heurística mais conservadora: muitas referências formatadas
    # Referências têm formato específico: [1] Autor, Título...
    ref_line_pattern = r"^\s*\[\d+\]\s+[A-Z]"
    ref_lines = len(re.findall(ref_line_pattern, text, re.MULTILINE))

    # Só considera referências se tiver MUITAS linhas nesse formato (>15)
    # E estiver no final do documento
    min_lines = getattr(_cfg, "PDF_REFERENCES_MIN_LINES", 15)
    references_end_ratio = getattr(_cfg, "PDF_REFERENCES_END_RATIO", 0.7)
    if ref_lines > min_lines and page_num > total_pages * references_end_ratio:
        return True

    return False


def analyze_pdf_pages(pdf_path: Path) -> list[dict]:
    """
    Analisa cada página do PDF e determina a melhor estratégia.
    Usa TOC (bookmarks) quando disponível para maior precisão.

    Args:
        pdf_path: Caminho do PDF

    Returns:
        Lista de dicts com info de cada página:
        {
            "page_num": int,
            "strategy": "image" | "text" | "skip" | "text_partial",
            "reason": str,
            "text_until": int | None  # Para text_partial: índice onde cortar o texto
        }
    """
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    analysis = []
    references_started = False

    # Tentar encontrar página de referências via TOC (mais preciso)
    toc_refs_page = _get_references_page_from_toc(doc)
    if toc_refs_page:
        print(f"      [INFO] TOC encontrado: Referências na página {toc_refs_page}")

    for page_num in range(total_pages):
        page = doc[page_num]
        page_number = page_num + 1  # 1-indexed

        # Primeira página: sempre texto (metadados do journal)
        if page_num == 0:
            analysis.append({
                "page_num": page_number,
                "strategy": "text",
                "reason": "Primeira página (metadados)",
                "text_until": None
            })
            continue

        # Verificar se chegou nas referências
        if not references_started:
            # Método 1: Via TOC (mais preciso)
            if toc_refs_page and page_number >= toc_refs_page:
                references_started = True

                # Se é a página exata onde referências começam, verificar conteúdo antes
                if page_number == toc_refs_page:
                    text = str(page.get_text())
                    refs_start = _find_references_start_in_text(text)

                    if refs_start and refs_start > 200:  # Tem conteúdo significativo antes
                        analysis.append({
                            "page_num": page_number,
                            "strategy": "text_partial",
                            "reason": f"Texto parcial (até referências)",
                            "text_until": refs_start
                        })
                        continue

            # Método 2: Via padrões de texto (fallback)
            elif not toc_refs_page and _is_references_page(page, page_number, total_pages):
                references_started = True

                # Verificar se há conteúdo antes das referências nesta página
                text = str(page.get_text())
                refs_start = _find_references_start_in_text(text)

                if refs_start and refs_start > 200:  # Tem conteúdo significativo antes
                    analysis.append({
                        "page_num": page_number,
                        "strategy": "text_partial",
                        "reason": f"Texto parcial (até referências)",
                        "text_until": refs_start
                    })
                    continue

        if references_started:
            analysis.append({
                "page_num": page_number,
                "strategy": "skip",
                "reason": "Seção de referências",
                "text_until": None
            })
            continue

        # Verificar se tem imagens relevantes
        if _has_relevant_images(page):
            analysis.append({
                "page_num": page_number,
                "strategy": "image",
                "reason": "Contém figuras/tabelas/gráficos",
                "text_until": None
            })
        else:
            analysis.append({
                "page_num": page_number,
                "strategy": "text",
                "reason": "Somente texto",
                "text_until": None
            })

    doc.close()
    return analysis


# =============================================================================
# FUNÇÕES DE EXTRAÇÃO HÍBRIDA
# =============================================================================

def extract_hybrid(
    pdf_path: Path,
    output_dir: Path,
    dpi: int = 150
) -> dict:
    """
    Extrai conteúdo do PDF usando estratégia híbrida.

    Args:
        pdf_path: Caminho do PDF
        output_dir: Diretório para salvar imagens
        dpi: Resolução para páginas com imagens

    Returns:
        Dict com:
        {
            "pages": [
                {"page_num": 1, "type": "text", "content": "..."},
                {"page_num": 2, "type": "image", "path": Path(...)},
                ...
            ],
            "analysis": [...],  # Resultado da análise
            "stats": {
                "total": int,
                "text_pages": int,
                "image_pages": int,
                "skipped_pages": int
            }
        }
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Analisar páginas
    analysis = analyze_pdf_pages(pdf_path)

    doc = fitz.open(str(pdf_path))
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    pages = []
    stats = {"total": len(doc), "text_pages": 0, "image_pages": 0, "skipped_pages": 0}

    for page_info in analysis:
        page_num = page_info["page_num"]
        strategy = page_info["strategy"]
        page = doc[page_num - 1]  # 0-indexed

        if strategy == "skip":
            stats["skipped_pages"] += 1
            continue

        if strategy == "text":
            text = str(page.get_text())
            pages.append({
                "page_num": page_num,
                "type": "text",
                "content": text.strip()
            })
            stats["text_pages"] += 1

        elif strategy == "text_partial":
            # Extrair texto apenas até o ponto indicado
            text = str(page.get_text())
            text_until = page_info.get("text_until")
            if text_until and text_until < len(text):
                text = text[:text_until]
            pages.append({
                "page_num": page_num,
                "type": "text",
                "content": text.strip()
            })
            stats["text_pages"] += 1

        elif strategy == "image":
            pix = page.get_pixmap(matrix=matrix)
            image_path = output_dir / f"page_{page_num:03d}.png"
            pix.save(str(image_path))
            pages.append({
                "page_num": page_num,
                "type": "image",
                "path": image_path
            })
            stats["image_pages"] += 1

    doc.close()

    return {
        "pages": pages,
        "analysis": analysis,
        "stats": stats
    }




def encode_image_base64(image_path: Path) -> str:
    """Codifica imagem em base64 para API."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_hybrid_content_for_anthropic(hybrid_result: dict) -> list[dict]:
    """
    Prepara conteúdo híbrido (texto + imagens) para API Anthropic.

    Args:
        hybrid_result: Resultado de extract_hybrid()

    Returns:
        Lista de content blocks para a API
    """
    content: list[dict[str, Any]] = []

    for page in hybrid_result["pages"]:
        page_num = page["page_num"]

        if page["type"] == "text":
            content.append({
                "type": "text",
                "text": f"--- Página {page_num} (texto) ---\n{page['content']}"
            })
        elif page["type"] == "image":
            content.append({
                "type": "text",
                "text": f"--- Página {page_num} (imagem com figuras/tabelas) ---"
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": encode_image_base64(page["path"])
                }
            })

    return content


def get_hybrid_content_for_openai(hybrid_result: dict, detail: str = "high") -> list[dict]:
    """
    Prepara conteúdo híbrido (texto + imagens) para API OpenAI.

    Args:
        hybrid_result: Resultado de extract_hybrid()
        detail: "high" ou "low"

    Returns:
        Lista de content blocks para a API
    """
    content: list[dict[str, Any]] = []

    for page in hybrid_result["pages"]:
        page_num = page["page_num"]

        if page["type"] == "text":
            content.append({
                "type": "text",
                "text": f"--- Página {page_num} (texto) ---\n{page['content']}"
            })
        elif page["type"] == "image":
            content.append({
                "type": "text",
                "text": f"--- Página {page_num} (imagem com figuras/tabelas) ---"
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encode_image_base64(page['path'])}",
                    "detail": detail
                }
            })

    return content


def get_images_for_anthropic(image_paths: list[Path]) -> list[dict]:
    """
    Prepara imagens no formato esperado pela API Anthropic.

    Returns:
        Lista de dicts com type, source.type, source.media_type, source.data
    """
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": encode_image_base64(p)
            }
        }
        for p in image_paths
    ]


def get_images_for_openai(image_paths: list[Path], detail: str = "high") -> list[dict]:
    """
    Prepara imagens no formato esperado pela API OpenAI.

    Args:
        image_paths: Lista de caminhos das imagens
        detail: "high" ou "low" (qualidade de análise)

    Returns:
        Lista de dicts no formato OpenAI vision
    """
    return [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{encode_image_base64(p)}",
                "detail": detail
            }
        }
        for p in image_paths
    ]


def get_pdf_info(pdf_path: Path) -> dict:
    """
    Retorna informações básicas do PDF.

    Returns:
        Dict com num_pages, title, author, etc.
    """
    doc = fitz.open(str(pdf_path))
    metadata = doc.metadata or {}
    info = {
        "num_pages": len(doc),
        "title": metadata.get("title", "") or "",
        "author": metadata.get("author", "") or "",
        "subject": metadata.get("subject", "") or "",
        "creator": metadata.get("creator", "") or "",
        "file_size_mb": pdf_path.stat().st_size / (1024 * 1024),
    }
    doc.close()
    return info




def check_pdf_quality(pdf_path: Path) -> dict:
    """
    Verifica qualidade do PDF para extração.

    Returns:
        Dict com métricas de qualidade
    """
    doc = fitz.open(str(pdf_path))

    total_chars = 0
    pages_with_text = 0
    pages_with_images = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = str(page.get_text())
        images = page.get_images()

        if len(text.strip()) > 100:
            pages_with_text += 1
        total_chars += len(text)

        if images:
            pages_with_images += 1

    num_pages = len(doc)
    doc.close()

    avg_chars_per_page = total_chars / num_pages if num_pages > 0 else 0

    return {
        "num_pages": num_pages,
        "pages_with_text": pages_with_text,
        "pages_with_images": pages_with_images,
        "total_chars": total_chars,
        "avg_chars_per_page": avg_chars_per_page,
        "is_likely_scanned": avg_chars_per_page < 500,  # Pouco texto = provavelmente escaneado
        "quality_score": "good" if avg_chars_per_page > 1000 else ("medium" if avg_chars_per_page > 500 else "low")
    }


# ============================================================
# Teste
# ============================================================

if __name__ == "__main__":
    import sys

    # Teste básico
    print("=== PDF Vision Module Test ===")

    # Se um caminho foi passado como argumento
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        if pdf_path.exists():
            print(f"\nAnalisando: {pdf_path.name}")

            info = get_pdf_info(pdf_path)
            print(f"  Páginas: {info['num_pages']}")
            print(f"  Título: {info['title'][:50] or 'N/A'}")
            print(f"  Tamanho: {info['file_size_mb']:.2f} MB")

            quality = check_pdf_quality(pdf_path)
            print(f"  Qualidade: {quality['quality_score']}")
            print(f"  Chars/página: {quality['avg_chars_per_page']:.0f}")
        else:
            print(f"Arquivo não encontrado: {pdf_path}")
    else:
        print("Uso: python pdf_vision.py <caminho_do_pdf>")
        print("\nFunções disponíveis:")
        print("  - extract_hybrid(pdf_path, output_dir, dpi=150)")
        print("  - get_images_for_anthropic(image_paths)")
        print("  - get_images_for_openai(image_paths)")
        print("  - get_pdf_info(pdf_path)")
        print("  - check_pdf_quality(pdf_path)")
