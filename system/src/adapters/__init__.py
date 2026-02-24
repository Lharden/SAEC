"""
Adapters para ferramentas locais de processamento.

Módulos:
- marker_adapter: Conversão PDF → Markdown via marker-pdf
- surya_adapter: OCR de alta qualidade via surya-ocr
- ollama_adapter: Cliente unificado para modelos Ollama
- rag_store: Vector store para RAG com ChromaDB
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import marker_adapter, ollama_adapter, rag_store, surya_adapter

__all__ = [
    "marker_adapter",
    "surya_adapter",
    "ollama_adapter",
    "rag_store",
]


def __getattr__(name: str) -> ModuleType:
    """Lazy-load de submódulos para preservar dependências opcionais."""
    if name in __all__:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
