# SAEC Code Audit: Pipeline Robustness + GUI Refactoring

**Date**: 2026-02-20
**Status**: Approved
**Approach**: Pipeline First, GUI Second

## Baseline

- 142/142 tests passing
- mypy: 0 errors across 71 files
- Python 3.14.2 (target 3.11+)
- ~39 core modules, ~20 GUI components

## Phase 1: Pipeline Hardening (7 tasks)

### P1. Eliminate `_is_placeholder_api_key` duplication
- **Current**: Identical function in `config.py:67-80` AND `pipeline_cascade.py:36-48`
- **Fix**: Delete from `pipeline_cascade.py`, import from `config`
- **Files**: `pipeline_cascade.py`
- **Risk**: Low

### P2. Unify `repair_yaml` fallback routing
- **Current**: `llm_client.py:691-798` has ~40 lines of manual if/elif provider fallback, duplicating `processors.py::_resolve_provider_for_task`
- **Fix**: Refactor `repair_yaml` to accept a resolved provider. Keep Ollama's multi-model chain (`_iter_ollama_repair_models`) but simplify control flow. Move routing decision to caller (`processors.py`).
- **Files**: `llm_client.py`, `processors.py`
- **Risk**: Medium (core logic change)

### P3. Add retry to `repair_yaml` calls
- **Current**: Direct `_call_openai_client()` / `self.anthropic.messages.create()` without retry
- **Fix**: Wrap repair calls with `_call_with_retry` pattern
- **Files**: `llm_client.py`
- **Risk**: Low

### P4. Fix empty `content=[]` in cascade API extraction
- **Current**: `pipeline_cascade.py:351` passes `content=[]` when no images. LLM receives intro text but zero article content.
- **Fix**: Build text content blocks from `text` parameter
- **Files**: `pipeline_cascade.py`
- **Risk**: Medium (behavior change)

### P5. Improve `_estimate_confidence`
- **Current**: Checks `"Contexto"`, `"Intervencao"` in raw YAML (won't match Portuguese field names)
- **Fix**: Check actual schema fields: `ArtigoID`, `ClasseIA`, `Mecanismo_Estruturado`, `Quotes`
- **Files**: `pipeline_cascade.py`
- **Risk**: Low

### P6. Make cascade reuse context/client
- **Current**: `extract_with_api` creates fresh `make_context()` + `LLMClient()` per call
- **Fix**: Accept optional `client: LLMClient` parameter
- **Files**: `pipeline_cascade.py`
- **Risk**: Low

### P7. Distinguish retriable vs fatal errors
- **Current**: Several `except Exception` blocks without distinguishing
- **Fix**: Catch specific exceptions where appropriate. Ensure `retriable` flag consistency.
- **Files**: `llm_client.py`, `pipeline_cascade.py`
- **Risk**: Low

## Phase 2: GUI Refactoring (5 tasks)

### G1. Extract `SessionManager`
- **Responsibility**: Session persistence (restore/persist state, on_close logic)
- **Source**: `app.py` lines ~334-425
- **Target**: `gui/session_manager.py`
- **Lines moved**: ~90

### G2. Extract `PipelineController`
- **Responsibility**: Run/cancel pipeline, progress handling, safety confirmations, mapping autofix
- **Source**: `app.py` lines ~939-1230
- **Target**: `gui/pipeline_controller.py`
- **Lines moved**: ~300

### G3. Extract `ProjectManager`
- **Responsibility**: Project CRUD, workspace management, env file I/O, articles browsing
- **Source**: `app.py` lines ~532-938
- **Target**: `gui/project_manager.py`
- **Lines moved**: ~350

### G4. Extract `QueueController`
- **Responsibility**: Queue UI refresh, history persistence, idle job start, elapsed time
- **Source**: `app.py` lines ~1230-1353
- **Target**: `gui/queue_controller.py`
- **Lines moved**: ~120

### G5. Thin shell `app.py`
- **Result**: app.py ~400 lines (init, menu, shortcuts, wiring, composition)
- **Pattern**: Composition - app owns controller instances
- **Contract**: Each controller receives references to UI elements it needs

## Testing Strategy

- Run full test suite after each task
- No new test files needed for Phase 1 (existing tests cover behavior)
- Phase 2: Ensure GUI smoke tests still pass after each extraction

## Success Criteria

- All 142 tests still pass after all changes
- mypy still clean
- app.py reduced from 1538 to ~400 lines
- No behavior changes (pure refactoring)
- Pipeline handles edge cases gracefully (empty content, provider unavailable, retry on repair)
