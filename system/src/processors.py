"""Processing utilities for article extraction."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Tuple

try:
    from .exceptions import ExtractError, ValidationError
    from .llm_client import LLMClient
    from .llm_utils import extract_yaml_from_response
    from .validators import validate_yaml, ValidationResult
    from .config import local_config
    from . import pdf_vision
except Exception:  # pragma: no cover - standalone usage
    from exceptions import ExtractError, ValidationError
    from llm_client import LLMClient
    from llm_utils import extract_yaml_from_response
    from validators import validate_yaml, ValidationResult
    from config import local_config
    import pdf_vision


class ArticleProcessor:
    """High-level extractor for a single article."""

    def __init__(
        self,
        *,
        client: LLMClient,
        guia_path: Path,
        output_dir: Path,
        work_dir: Path,
        logger: logging.Logger | None = None,
    ) -> None:
        self.client = client
        self.guia_path = guia_path
        self.output_dir = output_dir
        self.work_dir = work_dir
        self.logger = logger or logging.getLogger("saec")

    def _load_prompt(self) -> str:
        if not self.guia_path.exists():
            raise FileNotFoundError(f"Prompt não encontrado: {self.guia_path}")
        return self.guia_path.read_text(encoding="utf-8")

    def _load_texts(self, work_dir: Path) -> dict[str, str]:
        texts_path = work_dir / "texts.json"
        if not texts_path.exists():
            return {}
        data = json.loads(texts_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            texts = {str(k): str(v) for k, v in data.items()}
            return self._clean_texts(texts)
        return {}

    def _clean_texts(self, texts: dict[str, str]) -> dict[str, str]:
        """Remove linhas repetidas (headers/footers) para reduzir tokens sem perda semantica."""
        if not getattr(local_config, "STRIP_REPEATED_LINES", True):
            return texts

        if not texts:
            return texts

        # Coletar contagem de linhas por pagina
        line_counts: dict[str, int] = {}
        total_pages = 0
        for _, txt in texts.items():
            total_pages += 1
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            unique = set(lines)
            for line in unique:
                if len(line) <= local_config.REPEAT_LINE_MAX_LEN:
                    line_counts[line] = line_counts.get(line, 0) + 1

        if total_pages == 0:
            return texts

        min_frac = float(getattr(local_config, "REPEAT_LINE_MIN_FRACTION", 0.5))
        threshold = max(2, int(total_pages * min_frac))
        repeated = {line for line, c in line_counts.items() if c >= threshold}

        if not repeated:
            return texts

        cleaned: dict[str, str] = {}
        for k, txt in texts.items():
            new_lines = [l for l in txt.splitlines() if l.strip() not in repeated]
            cleaned[k] = "\n".join(new_lines).strip()

        return cleaned

    def _build_full_text(self, work_dir: Path) -> str:
        texts = self._load_texts(work_dir)
        if not texts:
            return ""
        parts: list[str] = []
        for key in sorted(
            texts.keys(), key=lambda x: int(x) if str(x).isdigit() else x
        ):
            parts.append(f"--- Pagina {key} ---")
            parts.append(texts[key])
            parts.append("")
        return "\n".join(parts).strip()

    def _build_hybrid_result(
        self, hybrid_meta: dict[str, Any], work_dir: Path
    ) -> dict[str, Any]:
        pages_info = hybrid_meta.get("pages_info", []) or []
        texts = self._load_texts(work_dir)

        pages: list[dict[str, Any]] = []
        for p in pages_info:
            page_num = int(p.get("page_num"))
            p_type = p.get("type")
            if p_type == "text":
                text = texts.get(str(page_num), "")
                pages.append({"page_num": page_num, "type": "text", "content": text})
            elif p_type == "image":
                raw_path = p.get("path")
                if raw_path:
                    image_path = Path(raw_path)
                else:
                    image_path = work_dir / "pages" / f"page_{page_num:03d}.png"
                pages.append(
                    {"page_num": page_num, "type": "image", "path": image_path}
                )

        pages = sorted(pages, key=lambda x: x["page_num"])
        return {
            "pages": pages,
            "analysis": hybrid_meta.get("analysis", []),
            "stats": hybrid_meta.get("stats", {}),
        }

    def _build_images_only_hybrid(
        self, hybrid_result: dict[str, Any]
    ) -> dict[str, Any]:
        pages = [p for p in hybrid_result.get("pages", []) if p.get("type") == "image"]
        return {
            "pages": pages,
            "analysis": hybrid_result.get("analysis", []),
            "stats": hybrid_result.get("stats", {}),
        }

    def _filter_text_blocks(self, content: list[dict], min_chars: int) -> list[dict]:
        """Remove blocos de texto muito curtos (opcional, para economizar tokens)."""
        if not min_chars or min_chars <= 0:
            return content

        filtered: list[dict] = []
        for block in content:
            if not isinstance(block, dict):
                filtered.append(block)
                continue
            if block.get("type") != "text":
                filtered.append(block)
                continue
            text = block.get("text") or ""
            # Manter marcadores de imagem e blocos especiais
            if "(imagem" in text or "RAG CONTEXT" in text:
                filtered.append(block)
                continue
            # Tentar extrair conteúdo após o header da página
            parts = text.split("\n", 1)
            payload = parts[1] if len(parts) > 1 else text
            if len(payload.strip()) >= min_chars:
                filtered.append(block)
        return filtered

    def _get_rag_context(self, *, artigo_id: str, work_dir: Path) -> str | None:
        if not getattr(local_config, "RAG_ENABLED", False):
            return None

        full_text = self._build_full_text(work_dir)
        if not full_text:
            return None

        try:
            import importlib

            try:
                rag_store = importlib.import_module(
                    ".adapters.rag_store", package=__package__
                )
            except Exception:  # pragma: no cover - standalone usage
                rag_store = importlib.import_module("adapters.rag_store")

            persist_dir = work_dir.parent / "rag_index"
            store = rag_store.get_default_store(persist_dir=persist_dir)

            indexed = set(store.list_articles())
            if artigo_id not in indexed:
                store.add_article(artigo_id, full_text)

            top_k = getattr(local_config, "RAG_TOP_K", 3)
            context_parts = [
                "[Contexto]",
                store.get_context_for_cimo(artigo_id, "context", top_k=top_k),
                "",
                "[Intervencao]",
                store.get_context_for_cimo(artigo_id, "intervention", top_k=top_k),
                "",
                "[Mecanismo]",
                store.get_context_for_cimo(artigo_id, "mechanism", top_k=top_k),
                "",
                "[Outcome]",
                store.get_context_for_cimo(artigo_id, "outcome", top_k=top_k),
            ]
            rag_text = "\n".join([p for p in context_parts if p])

            min_chars = getattr(local_config, "RAG_MIN_CONTEXT_CHARS", 1200)
            ratio = getattr(local_config, "RAG_MIN_CONTEXT_RATIO", 0.15)
            dynamic_min = max(min_chars, int(len(full_text) * float(ratio)))
            if len(rag_text) < dynamic_min:
                self.logger.warning(
                    "RAG context insuficiente, usando conteudo completo",
                    extra={"artigo_id": artigo_id, "provider": "-", "action": "rag"},
                )
                return None

            return rag_text
        except Exception as e:
            self.logger.warning(
                f"RAG falhou, usando conteudo completo: {e}",
                extra={"artigo_id": artigo_id, "provider": "-", "action": "rag"},
            )
            return None

    def prepare_content(
        self,
        hybrid_meta: dict[str, Any],
        work_dir: Path,
        provider: str,
    ) -> Tuple[list[dict], list[dict] | None]:
        hybrid_result = self._build_hybrid_result(hybrid_meta, work_dir)
        content_openai_full = pdf_vision.get_hybrid_content_for_openai(hybrid_result)
        content_anthropic_full = pdf_vision.get_hybrid_content_for_anthropic(
            hybrid_result
        )

        min_chars = getattr(self.client.llm_config, "PROMPT_MIN_TEXT_CHARS", 0)
        content_openai_llm = self._filter_text_blocks(content_openai_full, min_chars)
        content_anthropic_llm = self._filter_text_blocks(
            content_anthropic_full, min_chars
        )

        rag_context = self._get_rag_context(artigo_id=work_dir.name, work_dir=work_dir)
        if rag_context:
            images_only = self._build_images_only_hybrid(hybrid_result)
            content_openai_llm = pdf_vision.get_hybrid_content_for_openai(images_only)
            content_anthropic_llm = pdf_vision.get_hybrid_content_for_anthropic(
                images_only
            )

            rag_block = {
                "type": "text",
                "text": f"--- RAG CONTEXT (trechos mais relevantes) ---\n{rag_context}",
            }

            if provider == "anthropic":
                return [rag_block] + content_anthropic_llm, content_openai_full
            return [rag_block] + content_openai_llm, content_openai_full

        if provider == "anthropic":
            return content_anthropic_llm, content_openai_full
        return content_openai_llm, content_openai_full

    def _choose_fallback(self, primary: str) -> str:
        if primary == "anthropic":
            return "openai" if self.client.openai else "ollama"
        if primary == "openai":
            return "anthropic" if self.client.anthropic else "ollama"
        return "openai" if self.client.openai else "anthropic"

    def extract_with_llm(
        self,
        content: list[dict],
        *,
        artigo_id: str,
        provider: str,
        max_tokens: int = 8000,
    ) -> str:
        prompt = self._load_prompt()
        response = self.client.extract_with_hybrid(
            content=content,
            prompt=prompt,
            artigo_id=artigo_id,
            provider=provider,
            max_tokens=max_tokens,
        )
        return response

    def validate_and_repair(
        self,
        yaml_content: str,
        *,
        provider: str,
        artigo_id: str,
    ) -> Tuple[str, ValidationResult]:
        current = extract_yaml_from_response(yaml_content)
        current = self.client.postprocess_extraction(current, use_llm_format=False)
        result = validate_yaml(current)

        if result.is_valid:
            return current, result

        attempts = self.client.llm_config.MAX_REPAIR_ATTEMPTS
        last_result = result

        for _ in range(attempts):
            try:
                repaired = self.client.repair_yaml(
                    yaml_content=current,
                    errors=last_result.errors,
                    provider=provider,
                )
            except Exception as e:
                self.logger.warning(
                    "Repair falhou",
                    extra={
                        "artigo_id": artigo_id,
                        "provider": provider,
                        "action": "repair_yaml",
                    },
                )
                raise ExtractError(str(e)) from e

            current = extract_yaml_from_response(repaired)
            current = self.client.postprocess_extraction(current, use_llm_format=False)
            last_result = validate_yaml(current)
            if last_result.is_valid:
                return current, last_result

        return current, last_result

    def should_requote(self, result: ValidationResult) -> bool:
        """Decide se deve tentar reextração de quotes."""
        if not result or not hasattr(result, "errors"):
            return True
        errors = [str(e).lower() for e in result.errors]
        # Só requote se houver erros ligados a quotes
        return any("quote" in e or "trecho" in e or "pagina" in e for e in errors)

    def verify_quotes(
        self,
        *,
        yaml_content: str,
        content_openai: list[dict] | None,
        artigo_id: str,
        provider: str,
        validation_result: ValidationResult | None = None,
    ) -> Tuple[str, ValidationResult]:
        # Se já está válido, evitar reextração/quotes
        if validation_result and validation_result.is_valid:
            return yaml_content, validation_result
        # Se inválido, só requote quando os erros indicarem quotes
        if validation_result and not self.should_requote(validation_result):
            return yaml_content, validation_result

        fallback = self._choose_fallback(provider)
        return self.client.extract_validated_with_fallback(
            yaml_only=yaml_content,
            content_openai=content_openai,
            provider=provider,
            fallback_provider=fallback,
            max_attempts=2,
            max_tokens=4000,
        )

    def process_article(
        self,
        *,
        artigo_id: str,
        hybrid_meta: dict[str, Any],
        work_dir: Path,
        provider: str | None = None,
    ) -> Tuple[str, ValidationResult]:
        if provider is None:
            provider = self.client.llm_config.PRIMARY_PROVIDER

        content, content_openai = self.prepare_content(
            hybrid_meta=hybrid_meta,
            work_dir=work_dir,
            provider=provider,
        )

        try:
            if getattr(local_config, "USE_CASCADE", False):
                try:
                    from .pipeline_cascade import extract_cascade
                except ImportError:
                    from pipeline_cascade import extract_cascade

                prompt_template = self._load_prompt() + "\n\nTEXTO:\n{TEXT}\n"
                full_text = self._build_full_text(work_dir)
                if not full_text:
                    raw = self.extract_with_llm(
                        content, artigo_id=artigo_id, provider=provider
                    )
                else:
                    result = extract_cascade(
                        artigo_id=artigo_id,
                        text=full_text,
                        prompt_template=prompt_template,
                        strategy=local_config.EXTRACTION_STRATEGY,
                        images=None,
                    )
                    raw = result.yaml_content
            else:
                raw = self.extract_with_llm(
                    content, artigo_id=artigo_id, provider=provider
                )
        except Exception as e:
            raise ExtractError(str(e)) from e

        repaired, result = self.validate_and_repair(
            yaml_content=raw,
            provider=provider,
            artigo_id=artigo_id,
        )

        final_yaml, final_result = self.verify_quotes(
            yaml_content=repaired,
            content_openai=content_openai,
            artigo_id=artigo_id,
            provider=provider,
            validation_result=result,
        )

        if not final_result.is_valid:
            self.logger.warning(
                "YAML invalido apos reparos",
                extra={
                    "artigo_id": artigo_id,
                    "provider": provider,
                    "action": "validate",
                },
            )
            raise ValidationError("YAML ainda invalido apos reparos")

        return final_yaml, final_result
