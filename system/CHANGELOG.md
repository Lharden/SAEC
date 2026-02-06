# Changelog

## [Unreleased] — 2026-02-04

### Added
- `run_pipeline.ps1` com modo interativo, confirmação e logs automáticos.
- `run_pipeline.bat` como wrapper para execução simplificada no Windows.
- `llm_client_types.py`, `llm_client_postprocess.py`, `llm_client_quotes.py` e `llm_utils.py` para modularizar o cliente LLM.
- `qa_utils.py` com utilitários compartilhados de QA.

### Changed
- `mapping_sync.py` agora sincroniza com base em **validação + QA OK** (método recomendado).
- Consolidação pode filtrar por QA OK.
- `config.py` reorganizado para leitura/uso consistente de variáveis de ambiente.
- `README.md` atualizado com diagrama do pipeline e instruções consolidadas.

### Removed
- Funções legacy de `pdf_vision.py` (`render_pdf_pages` e `extract_text_simple`).
- `sync_mapping_with_yamls(...)` (fluxo legado).
- `OLLAMA_MODEL` (fallback legado) — substituído por `OLLAMA_MODEL_CODER`/`OLLAMA_MODEL_VISION`.
- `test_api.py` (utilitário legado).
