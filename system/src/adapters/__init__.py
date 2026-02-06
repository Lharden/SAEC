"""
Adapters para ferramentas locais de processamento.

Módulos:
- marker_adapter: Conversão PDF → Markdown via marker-pdf
- surya_adapter: OCR de alta qualidade via surya-ocr
- ollama_adapter: Cliente unificado para modelos Ollama
- rag_store: Vector store para RAG com ChromaDB
"""

from __future__ import annotations

__all__ = [
    "marker_adapter",
    "surya_adapter",
    "ollama_adapter",
    "rag_store",
]
