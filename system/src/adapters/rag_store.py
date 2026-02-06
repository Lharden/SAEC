"""
RAG Store - Vector store para busca semântica em artigos.

Funcionalidades:
- Indexação de artigos em chunks
- Busca semântica com embeddings
- Reranking de resultados
- Persistência local com ChromaDB
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    from ..exceptions import SAECError
except ImportError:  # pragma: no cover - standalone usage
    from exceptions import SAECError

logger = logging.getLogger(__name__)


# ============================================================
# Exceções
# ============================================================

class RAGError(SAECError):
    """Erro relacionado ao RAG store."""
    pass


# ============================================================
# Data Classes
# ============================================================

@dataclass
class Chunk:
    """Chunk de texto de um artigo."""
    id: str
    text: str
    artigo_id: str
    page_number: int
    section: str | None = None
    char_start: int = 0
    char_end: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """Resultado de busca no RAG."""
    chunk: Chunk
    score: float
    distance: float


@dataclass
class RAGConfig:
    """Configuração do RAG store."""
    persist_dir: Path = field(default_factory=lambda: Path("./rag_index"))
    embedding_model: str = "nomic-embed-text-v2-moe:latest"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    collection_name: str = "saec_articles"


# ============================================================
# Chunking
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[tuple[str, int, int]]:
    """
    Divide texto em chunks com overlap.

    Args:
        text: Texto para dividir
        chunk_size: Tamanho máximo de cada chunk
        chunk_overlap: Overlap entre chunks

    Returns:
        Lista de (chunk_text, start_pos, end_pos)
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Tentar quebrar em fim de sentença ou parágrafo
        if end < text_len:
            # Procurar ponto final, quebra de linha, etc.
            for sep in ["\n\n", "\n", ". ", "! ", "? "]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + chunk_size // 2:
                    end = last_sep + len(sep)
                    break

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append((chunk_text, start, end))

        # Próximo chunk com overlap
        start = end - chunk_overlap
        if start >= text_len - chunk_overlap:
            break

    return chunks


def chunk_by_sections(
    text: str,
    max_chunk_size: int = 2000,
) -> list[tuple[str, str | None]]:
    """
    Divide texto por seções (headers markdown).

    Args:
        text: Texto markdown
        max_chunk_size: Tamanho máximo por chunk

    Returns:
        Lista de (chunk_text, section_name)
    """
    # Padrão para headers markdown
    header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    sections = []
    current_section = None
    current_text = []
    current_start = 0

    lines = text.split('\n')
    pos = 0

    for line in lines:
        header_match = header_pattern.match(line)

        if header_match:
            # Salvar seção anterior
            if current_text:
                section_text = '\n'.join(current_text).strip()
                if section_text:
                    sections.append((section_text, current_section))

            current_section = header_match.group(2).strip()
            current_text = [line]
        else:
            current_text.append(line)

        pos += len(line) + 1

    # Última seção
    if current_text:
        section_text = '\n'.join(current_text).strip()
        if section_text:
            sections.append((section_text, current_section))

    # Subdividir seções muito grandes
    result = []
    for section_text, section_name in sections:
        if len(section_text) <= max_chunk_size:
            result.append((section_text, section_name))
        else:
            # Subdividir
            sub_chunks = chunk_text(section_text, max_chunk_size, max_chunk_size // 5)
            for chunk, start, end in sub_chunks:
                result.append((chunk, section_name))

    return result


# ============================================================
# RAG Store
# ============================================================

class RAGStore:
    """
    Vector store para artigos SAEC.

    Usa ChromaDB para persistência local e embeddings via Ollama.
    """

    def __init__(
        self,
        config: RAGConfig | None = None,
    ):
        """
        Inicializa RAG store.

        Args:
            config: Configuração opcional
        """
        self.config = config or RAGConfig()
        self._client = None
        self._collection = None
        self._embedding_cache: dict[str, list[float]] = {}

    def _ensure_initialized(self):
        """Garante que ChromaDB está inicializado."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings

                self.config.persist_dir.mkdir(parents=True, exist_ok=True)

                self._client = chromadb.PersistentClient(
                    path=str(self.config.persist_dir),
                    settings=Settings(anonymized_telemetry=False),
                )

                self._collection = self._client.get_or_create_collection(
                    name=self.config.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )

                logger.info(f"RAG store inicializado em {self.config.persist_dir}")

            except ImportError:
                raise RAGError("chromadb não está instalado. Execute: pip install chromadb")
            except Exception as e:
                raise RAGError(f"Erro ao inicializar ChromaDB: {e}")

    def _get_embedding(self, text: str) -> list[float]:
        """Gera embedding para texto."""
        # Cache por hash do texto
        text_hash = hashlib.md5(text.encode()).hexdigest()
        if text_hash in self._embedding_cache:
            return self._embedding_cache[text_hash]

        try:
            from . import ollama_adapter

            result = ollama_adapter.generate_embedding(
                text,
                model=self.config.embedding_model,
            )
            embedding = result.embedding

            # Cache
            self._embedding_cache[text_hash] = embedding
            return embedding

        except Exception as e:
            raise RAGError(f"Erro ao gerar embedding: {e}")

    def _get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings em batch."""
        try:
            from . import ollama_adapter

            results = ollama_adapter.generate_embeddings_batch(
                texts,
                model=self.config.embedding_model,
            )
            return [r.embedding for r in results]

        except Exception as e:
            raise RAGError(f"Erro ao gerar embeddings batch: {e}")

    def add_article(
        self,
        artigo_id: str,
        text: str,
        *,
        metadata: dict | None = None,
        use_sections: bool = True,
    ) -> int:
        """
        Adiciona artigo ao índice.

        Args:
            artigo_id: ID do artigo
            text: Texto completo do artigo
            metadata: Metadados adicionais
            use_sections: Usar chunking por seções

        Returns:
            Número de chunks adicionados
        """
        self._ensure_initialized()
        assert self._collection is not None  # garantido por _ensure_initialized

        # Remover artigo existente se houver
        self.delete_article(artigo_id)

        # Dividir em chunks
        if use_sections:
            raw_chunks = chunk_by_sections(text, self.config.chunk_size)
        else:
            raw_chunks = [(c, None) for c, _, _ in chunk_text(
                text, self.config.chunk_size, self.config.chunk_overlap
            )]

        if not raw_chunks:
            logger.warning(f"Nenhum chunk gerado para {artigo_id}")
            return 0

        # Preparar dados para ChromaDB
        ids = []
        documents = []
        metadatas = []

        for i, (chunk_text, section) in enumerate(raw_chunks):
            chunk_id = f"{artigo_id}_chunk_{i:04d}"
            ids.append(chunk_id)
            documents.append(chunk_text)

            chunk_meta = {
                "artigo_id": artigo_id,
                "chunk_index": i,
                "section": section or "",
                "char_count": len(chunk_text),
            }
            if metadata:
                chunk_meta.update(metadata)
            metadatas.append(chunk_meta)

        # Gerar embeddings em batch
        logger.info(f"Gerando embeddings para {len(documents)} chunks de {artigo_id}...")
        embeddings = self._get_embeddings_batch(documents)

        # Adicionar ao ChromaDB
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(f"Adicionados {len(ids)} chunks de {artigo_id}")
        return len(ids)

    def delete_article(self, artigo_id: str) -> bool:
        """
        Remove artigo do índice.

        Args:
            artigo_id: ID do artigo

        Returns:
            True se removeu algo
        """
        self._ensure_initialized()
        assert self._collection is not None  # garantido por _ensure_initialized

        try:
            # Buscar chunks do artigo
            results = self._collection.get(
                where={"artigo_id": artigo_id},
            )

            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                logger.info(f"Removidos {len(results['ids'])} chunks de {artigo_id}")
                return True

            return False

        except Exception as e:
            logger.warning(f"Erro ao remover artigo {artigo_id}: {e}")
            return False

    def search(
        self,
        query: str,
        *,
        artigo_id: str | None = None,
        top_k: int = 5,
        rerank: bool = False,
    ) -> list[SearchResult]:
        """
        Busca chunks relevantes.

        Args:
            query: Query de busca
            artigo_id: Filtrar por artigo específico
            top_k: Número de resultados
            rerank: Usar reranking para melhorar resultados

        Returns:
            Lista de SearchResult ordenados por relevância
        """
        self._ensure_initialized()
        assert self._collection is not None  # garantido por _ensure_initialized

        try:
            # Gerar embedding da query
            query_embedding = self._get_embedding(query)

            # Preparar filtro
            where_filter = None
            if artigo_id:
                where_filter = {"artigo_id": artigo_id}

            # Buscar no ChromaDB
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2 if rerank else top_k,  # Buscar mais se for rerankar
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            # Converter para SearchResult
            search_results = []
            for i, doc_id in enumerate(results["ids"][0]):
                chunk = Chunk(
                    id=doc_id,
                    text=results["documents"][0][i],
                    artigo_id=results["metadatas"][0][i].get("artigo_id", ""),
                    page_number=results["metadatas"][0][i].get("page_number", 0),
                    section=results["metadatas"][0][i].get("section"),
                    metadata=results["metadatas"][0][i],
                )

                distance = results["distances"][0][i]
                score = 1.0 - distance  # Converter distância para score

                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    distance=distance,
                ))

            # Reranking opcional
            if rerank and len(search_results) > top_k:
                search_results = self._rerank(query, search_results, top_k)

            return search_results[:top_k]

        except Exception as e:
            logger.error(f"Erro na busca RAG: {e}")
            raise RAGError(f"Search failed: {e}")

    def _rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Reordena resultados usando reranker."""
        try:
            from . import ollama_adapter

            passages = [r.chunk.text for r in results]
            rerank_result = ollama_adapter.rerank_passages(
                query,
                passages,
                top_k=top_k,
            )

            # Reordenar
            reranked = []
            for idx, score in rerank_result.rankings:
                result = results[idx]
                result.score = score
                reranked.append(result)

            return reranked

        except Exception as e:
            logger.warning(f"Reranking falhou, usando ordem original: {e}")
            return results

    def get_context_for_cimo(
        self,
        artigo_id: str,
        component: Literal["context", "intervention", "mechanism", "outcome", "all"],
        top_k: int = 3,
    ) -> str:
        """
        Obtém contexto relevante para extração CIMO.

        Args:
            artigo_id: ID do artigo
            component: Componente CIMO a extrair
            top_k: Número de chunks

        Returns:
            Texto concatenado dos chunks mais relevantes
        """
        # Queries otimizadas para cada componente CIMO
        queries = {
            "context": "problem context background industry sector challenges issues",
            "intervention": "solution method approach technology implementation AI machine learning",
            "mechanism": "how it works process mechanism causal relationship",
            "outcome": "results outcomes benefits performance improvement metrics",
            "all": "problem solution method results AI supply chain",
        }

        query = queries.get(component, queries["all"])

        results = self.search(
            query,
            artigo_id=artigo_id,
            top_k=top_k,
            rerank=True,
        )

        if not results:
            return ""

        # Concatenar chunks
        context_parts = []
        for i, result in enumerate(results, 1):
            section = result.chunk.section or "N/A"
            context_parts.append(f"[Trecho {i} - {section}]")
            context_parts.append(result.chunk.text)
            context_parts.append("")

        return "\n".join(context_parts)

    def list_articles(self) -> list[str]:
        """Lista todos os artigos indexados."""
        self._ensure_initialized()
        assert self._collection is not None  # garantido por _ensure_initialized

        try:
            # Buscar todos os metadados únicos
            results = self._collection.get(
                include=["metadatas"],
            )

            artigo_ids = set()
            for meta in results["metadatas"]:
                if "artigo_id" in meta:
                    artigo_ids.add(meta["artigo_id"])

            return sorted(artigo_ids)

        except Exception as e:
            logger.error(f"Erro ao listar artigos: {e}")
            return []

    def get_stats(self) -> dict:
        """Retorna estatísticas do índice."""
        self._ensure_initialized()
        assert self._collection is not None  # garantido por _ensure_initialized

        try:
            count = self._collection.count()
            articles = self.list_articles()

            return {
                "total_chunks": count,
                "total_articles": len(articles),
                "articles": articles,
                "persist_dir": str(self.config.persist_dir),
                "embedding_model": self.config.embedding_model,
            }

        except Exception as e:
            return {"error": str(e)}


# ============================================================
# Funções de Conveniência
# ============================================================

_default_store: RAGStore | None = None


def get_default_store(persist_dir: Path | None = None) -> RAGStore:
    """Obtém instância padrão do RAG store."""
    global _default_store

    if _default_store is None:
        config = RAGConfig()
        if persist_dir:
            config.persist_dir = persist_dir
        _default_store = RAGStore(config)

    return _default_store


def index_article(
    artigo_id: str,
    text: str,
    persist_dir: Path | None = None,
) -> int:
    """Indexa um artigo no store padrão."""
    store = get_default_store(persist_dir)
    return store.add_article(artigo_id, text)


def search_articles(
    query: str,
    artigo_id: str | None = None,
    top_k: int = 5,
    persist_dir: Path | None = None,
) -> list[SearchResult]:
    """Busca no store padrão."""
    store = get_default_store(persist_dir)
    return store.search(query, artigo_id=artigo_id, top_k=top_k)


# ============================================================
# CLI Test
# ============================================================

if __name__ == "__main__":
    print("=== RAG Store Test ===\n")

    # Testar chunking
    sample_text = """
# Introduction

This is the introduction section with some text about the problem.
The problem is complex and requires a sophisticated solution.

# Methods

We propose a novel approach using machine learning.
The method involves several steps including data preprocessing.

## Data Collection

Data was collected from multiple sources.

## Model Training

The model was trained using deep learning techniques.

# Results

Our approach achieved significant improvements.
The results show a 30% increase in performance.

# Conclusion

In conclusion, our method is effective.
"""

    print("Testando chunking por seções...")
    chunks = chunk_by_sections(sample_text, max_chunk_size=500)
    print(f"  Chunks gerados: {len(chunks)}")
    for i, (text, section) in enumerate(chunks):
        print(f"  [{i}] {section}: {len(text)} chars")

    print("\nTestando RAG store...")
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            config = RAGConfig(persist_dir=Path(tmpdir))
            store = RAGStore(config)

            # Adicionar artigo de teste
            n_chunks = store.add_article("TEST_001", sample_text)
            print(f"  Chunks indexados: {n_chunks}")

            # Buscar
            results = store.search("machine learning method", top_k=2)
            print(f"  Resultados de busca: {len(results)}")
            for r in results:
                print(f"    - Score {r.score:.3f}: {r.chunk.text[:50]}...")

            # Stats
            stats = store.get_stats()
            print(f"  Stats: {stats}")

    except Exception as e:
        print(f"  Erro: {e}")
