"""
Extração de artigo científico via LiteLLM proxy com suporte a texto e visão.

Uso:
    python extract_article.py --article ART_001 --model claude-sonnet --output ./yamls
    python extract_article.py --article ART_001 --model gemini-pro --output ./yamls --max-images 6
    python extract_article.py --article ART_001 --model kimi-k2.5 --output ./yamls --text-only
"""
import argparse
import base64
import json
import logging
import os
import re
import sys
from pathlib import Path

import yaml

# Paths calculados a partir da localização do script
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent.parent  # 00 Dados RSL
WORK_DIR = _ROOT / "data" / "Extraction" / "outputs" / "work"
GUIA_PATH = _ROOT / "data" / "Extraction" / "Guia_Extracao_v3_3.md"

LITELLM_BASE_URL = "http://localhost:4000"
LITELLM_API_KEY = os.environ.get("LITELLM_API_KEY", "test-local-proxy")
DEFAULT_MAX_TOKENS = 8192
DEFAULT_MAX_IMAGES = 8

log = logging.getLogger(__name__)


def _load_article_data(article_id: str) -> tuple[dict, dict]:
    """Carrega hybrid.json e texts.json do artigo já ingerido."""
    article_dir = WORK_DIR / article_id
    if not article_dir.exists():
        raise FileNotFoundError(
            f"Artigo não ingerido: {article_dir}\n"
            f"Execute primeiro o step 2 (ingestão) do SAEC."
        )
    hybrid = json.loads((article_dir / "hybrid.json").read_text(encoding="utf-8"))
    texts = json.loads((article_dir / "texts.json").read_text(encoding="utf-8"))
    return hybrid, texts


def _build_content_parts(
    article_id: str,
    hybrid: dict,
    texts: dict,
    text_only: bool,
    max_images: int,
) -> list[dict]:
    """Monta partes do conteúdo (texto + imagens) para a mensagem do LLM."""
    parts: list[dict] = [
        {"type": "text", "text": f"Extraia os dados do artigo {article_id} seguindo rigorosamente o Guia e o framework CIMO.\n\n"}
    ]

    pages_info = hybrid.get("pages_info", [])
    image_count = 0

    for page in pages_info:
        page_num = page.get("page_num")
        page_type = page.get("type", "text")

        if page_type == "text":
            text = texts.get(str(page_num), "")
            if text and text.strip():
                parts.append({"type": "text", "text": f"\n--- Página {page_num} ---\n{text}\n"})

        elif page_type == "image" and not text_only:
            if image_count >= max_images:
                parts.append({"type": "text", "text": f"\n[Página {page_num}: imagem omitida — limite de {max_images} atingido]\n"})
                continue
            img_path_str = page.get("path")
            if img_path_str:
                img_path = Path(img_path_str)
                if img_path.exists():
                    b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
                    parts.append({"type": "text", "text": f"\n--- Página {page_num} (imagem) ---\n"})
                    parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
                    image_count += 1
                else:
                    log.warning(f"Imagem não encontrada: {img_path}")

    log.info(f"Conteúdo montado: {len([p for p in parts if p['type'] == 'text'])} blocos de texto, {image_count} imagens")
    return parts


def _extract_yaml_from_response(text: str) -> str:
    """Extrai bloco YAML da resposta do LLM, removendo markdown e texto extra."""
    text = text.strip()

    # Remove markdown code blocks
    match = re.search(r"```(?:yaml)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Já começa com delimitador ou campo YAML
    if text.startswith("---") or text.startswith("ArtigoID"):
        return text

    # Busca início do YAML no meio da resposta
    idx = text.find("ArtigoID:")
    if idx != -1:
        return text[idx:]

    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Extração CIMO via LiteLLM proxy")
    parser.add_argument("--article", required=True, help="Ex: ART_001")
    parser.add_argument("--model", required=True, help="Model name no LiteLLM (ex: claude-sonnet)")
    parser.add_argument("--output", required=True, help="Diretório de saída para os YAMLs")
    parser.add_argument("--base-url", default=LITELLM_BASE_URL, help="URL do proxy LiteLLM")
    parser.add_argument("--max-images", type=int, default=DEFAULT_MAX_IMAGES, help="Máximo de imagens incluídas")
    parser.add_argument("--text-only", action="store_true", help="Ignora imagens (para modelos text-only)")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler()],
    )

    try:
        import openai
    except ImportError:
        log.error("openai não instalado. Execute: pip install openai")
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"=== Extração: {args.article} | Modelo: {args.model} ===")

    # Carregar dados ingeridos
    try:
        hybrid, texts = _load_article_data(args.article)
    except FileNotFoundError as exc:
        log.error(str(exc))
        return 1

    # Carregar guia completo
    if not GUIA_PATH.exists():
        log.error(f"Guia não encontrado: {GUIA_PATH}")
        return 1
    guia = GUIA_PATH.read_text(encoding="utf-8")

    # Montar system prompt com o guia
    system_prompt = (
        "Você é um especialista em extração estruturada de artigos científicos "
        "sobre IA aplicada a Supply Chain Management no setor Oil & Gas.\n\n"
        f"{guia}\n\n"
        "INSTRUÇÃO FINAL: Responda APENAS com o YAML completo e estruturado. "
        "Sem texto introdutório, sem explicações, sem markdown code blocks. "
        "Comece diretamente com '---' ou 'ArtigoID:'."
    )

    # Montar conteúdo do usuário
    content_parts = _build_content_parts(
        args.article, hybrid, texts, args.text_only, args.max_images
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_parts},
    ]

    # Chamar LiteLLM proxy
    client = openai.OpenAI(api_key=LITELLM_API_KEY, base_url=args.base_url)

    try:
        response = client.chat.completions.create(
            model=args.model,
            messages=messages,
            max_tokens=args.max_tokens,
            temperature=0.1,
        )
    except openai.APIError as exc:
        log.error(f"Erro na API LiteLLM: {exc}")
        return 1

    raw = response.choices[0].message.content or ""
    if not raw.strip():
        log.error("Resposta vazia do modelo")
        return 1

    yaml_content = _extract_yaml_from_response(raw)

    # Validação básica de parse
    try:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            log.warning("Resposta parseada não é um dicionário — verifique o YAML manualmente")
    except yaml.YAMLError as exc:
        log.warning(f"YAML com problemas de parse: {exc}")

    # Salvar YAML
    out_yaml = output_dir / f"{args.article}.yaml"
    out_yaml.write_text(yaml_content, encoding="utf-8")
    log.info(f"YAML salvo: {out_yaml}")

    # Salvar metadata de execução
    images_included = sum(1 for p in content_parts if p.get("type") == "image_url")
    meta = {
        "article_id": args.article,
        "model": args.model,
        "base_url": args.base_url,
        "images_included": images_included,
        "text_only": args.text_only,
        "tokens_input": getattr(response.usage, "prompt_tokens", None),
        "tokens_output": getattr(response.usage, "completion_tokens", None),
        "tokens_total": getattr(response.usage, "total_tokens", None),
    }
    meta_path = output_dir / f"{args.article}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Metadata salva: {meta_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
