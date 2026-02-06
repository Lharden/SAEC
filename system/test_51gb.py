"""Teste de extração com qwen3-coder-next (51GB)."""

import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.config import paths
from src.adapters import ollama_adapter

def main():
    # Carregar texto
    texts_file = paths.WORK / "ART_001" / "texts.json"
    with open(texts_file, encoding="utf-8") as f:
        texts = json.load(f)
    full_text = "\n".join(texts.values())[:35000]

    # Prompt otimizado
    prompt = """You are a structured data extractor. Extract information from the scientific article below into the EXACT YAML format shown.

CRITICAL RULES:
1. Output ONLY the YAML, no explanations
2. Start with --- and end with ---
3. Use "NR" for missing information
4. Quotes must be EXACT text from the article

REQUIRED YAML FORMAT:
---
ArtigoID: ART_001
Ano: 2026
Referencia: "Authors, Year"
SegmentoOG: Downstream
ProcessoSCM: "supplier selection"

Problema: "Description of the business problem in 2-3 sentences"

ClasseIA: Hybrid
Tarefa: Classification
Modelos: "list of AI/ML models used"
Maturidade: Pilot

Intervencao: "Description of the proposed solution in 2-3 sentences"

Mecanismo: "Explanation of how the solution works"

Resultados_Quant: "Numerical results: accuracy 92%, etc"
Resultados_Qual: "Qualitative benefits described"

Limitacoes: "Limitations mentioned by authors"

Quotes:
- ID: Q1
  Tipo: Context
  Texto: "exact quote about the problem from the text"
  Pagina: 1
- ID: Q2
  Tipo: Intervention
  Texto: "exact quote about the solution from the text"
  Pagina: 2
- ID: Q3
  Tipo: Outcome
  Texto: "exact quote about results from the text"
  Pagina: 8
---

ARTICLE TEXT:
""" + full_text + """

OUTPUT (YAML only, starting with ---):"""

    print(f"Texto: {len(full_text):,} chars")
    print(f"Prompt total: {len(prompt):,} chars")
    print()
    print("Testando qwen3-coder-next (51GB)...")
    print("Isso pode demorar alguns minutos...")
    print()

    start = time.time()
    response = ollama_adapter.generate_text(
        prompt,
        model="qwen3-coder-next:latest",
        temperature=0.1,
        max_tokens=3000,
    )
    elapsed = time.time() - start

    print(f"Tempo: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Tokens: {response.total_tokens}")

    # Salvar resultado
    out_path = paths.WORK / "ART_001" / "cascade_next51gb.yaml"
    out_path.write_text(response.content, encoding="utf-8")
    print(f"Salvo em: {out_path.name}")
    print()
    print("=== RESULTADO ===")
    print(response.content[:2500])


if __name__ == "__main__":
    main()
