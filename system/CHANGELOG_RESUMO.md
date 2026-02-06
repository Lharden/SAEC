# Resumo Executivo — Atualizações Recentes (2026-02-04)

## O que mudou (alto nível)
- Pipeline ficou **mais robusto**: aprovação agora exige **YAML válido + QA OK**.
- Cliente LLM foi **modularizado**, com manutenção mais simples e risco menor.
- Scripts de execução ficaram **interativos e rastreáveis** (logs automáticos).
- Remoção de funções legacy que não eram mais usadas.

## Impacto prático
- Menos falsos positivos no `mapping.csv`.
- Consolidação mais confiável (somente dados validados e com QA ok).
- Operação mais guiada e segura via `run_pipeline.ps1/.bat`.

## Entregas principais
- `run_pipeline.ps1` com menu interativo e confirmação.
- `run_pipeline.bat` como wrapper simples no Windows.
- `llm_client_*` dividido em módulos (tipos, pós-processo, quotes).
- `qa_utils.py` para consolidar lógica de QA.

## Remoções (legacy)
- `render_pdf_pages` e `extract_text_simple` (PDF).
- `sync_mapping_with_yamls` (sync antigo).
- `OLLAMA_MODEL` (fallback antigo).
- `test_api.py`.

## Status de qualidade
- `mypy`: OK  
- `pyright`: OK  
- `pylint`: 10.00/10
