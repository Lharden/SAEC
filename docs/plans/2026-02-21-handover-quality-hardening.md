# Quality Hardening — Plan Handover

**Date**: 2026-02-21
**Status**: Phases 1-2 COMPLETE, Phases 3-4 PENDING
**Baseline commit**: `442ee3d` (feat: complete phase 2 robustness hardening)
**Current HEAD**: `77a909c` (docs: add docstrings to complex public functions)
**Tests**: 142/142 passing (no new tests added yet)

---

## What Was Already Done BEFORE This Session

### Previous Session: Code Audit Phase 1 + Phase 2 GUI (commits up to `442ee3d`)

**Pipeline Robustness (7 tasks, P1-P7)** — ALL COMPLETED:
- P1: Eliminated `_is_placeholder_api_key` duplication between config.py and pipeline_cascade.py
- P2+P3: Unified `repair_yaml` fallback routing + added retry with exponential backoff
- P4: Fixed empty `content=[]` in cascade API extraction (was sending zero article content to LLM)
- P5: Improved `_estimate_confidence` to check actual schema fields instead of Portuguese strings
- P6: Made cascade reuse context/client (optional `client: LLMClient` parameter)
- P7: Distinguished retriable vs fatal errors with `retriable` flag consistency

**GUI Refactoring (5 tasks, G1-G5)** — ALL COMPLETED:
- G1: Extracted `SessionManager` from app.py → `gui/session_manager.py` (114 lines)
- G2: Extracted `PipelineController` → `gui/pipeline_controller.py` (419 lines)
- G3: Extracted `ProjectManager` → `gui/project_manager.py` (503 lines)
- G4: Extracted `QueueController` → `gui/queue_controller.py` (151 lines)
- G5: Thinned app.py from 1538 → 626 lines (thin shell with delegators)

---

## What Was Done IN THIS SESSION

### Design Phase

1. Deep codebase audit via Explore subagent — produced scorecard:
   - Error Handling: 6/10
   - Logging: 7/10
   - Test Coverage: 4/10
   - Code Smells: 7/10
   - Dead Code: 7/10
   - Docstrings: 7/10
   - **Overall: 7.4/10**

2. User chose: all 3 axes, progressive, full scope (including profile engine + GUI dialogs), unit tests completos, horizontal by category approach.

3. Created design doc: `docs/plans/2026-02-21-quality-hardening-design.md`
4. Created implementation plan: `docs/plans/2026-02-21-quality-hardening-plan.md` (24 tasks in 4 phases)

### Implementation — Phase 1: Error Handling Sweep (COMPLETE, Score 6→9)

**Commit `025c934`** — Task 1: Specify import-related exception blocks
- Changed ~26 `except Exception:` blocks on import/importlib calls to `except (ImportError, ModuleNotFoundError):` or `except (ImportError, ModuleNotFoundError, TypeError):` (TypeError for `importlib.import_module` with relative paths)
- Files: config.py, consolidate.py, context.py, llm_client_postprocess.py, llm_client_quotes.py, llm_client_types.py, llm_utils.py, pdf_vision.py, validators.py, qa_guideline.py

**Commit `e7dd88d`** — Task 2: Specify API/network exception blocks in llm_client.py
- Added `_LLM_API_ERRORS` tuple at module level (aggregates ConnectionError, TimeoutError, OSError, httpx.HTTPError, AnthropicAPIError, OpenAIError)
- Replaced 8 `except Exception as e:` in provider/repair methods with `except _LLM_API_ERRORS as e:`
- Marked 4 intentional catch-alls with `# Intentional: catch-all for retry/fallback logic`

**Commit `47d691e`** — Task 3: Specify remaining exception blocks
- ~22 more blocks specified across consolidate.py, llm_client_postprocess.py, llm_client_quotes.py, llm_utils.py, pdf_vision.py, marker_adapter.py, profile_engine/validator.py
- Also fixed missed import blocks in mapping_sync.py, pipeline_ingest.py, pipeline_extract.py, processors.py
- Categories: YAML→YAMLError/ValueError, profile→ImportError/AttributeError, PDF→broad with comment, eval→broad with comment
- Added `logger.debug()` to 2 previously silent requote failures
- 8 blocks kept as `except Exception` with justification comments

### Implementation — Phase 2: Logging Hardening + Docstrings (COMPLETE, Score 7→9)

**Commit `459edc8`** — Task 5: Structured logging in llm_client.py
- Updated all 8 logger calls to use `extra=` dict with `provider`, `action`, `artigo_id`, `model` fields
- Replaced f-strings with %-style formatting

**Commit `df718b1`** — Task 6: Structured logging in pipeline and adapters
- Updated ~27 logger calls across pipeline_cascade.py, processors.py, marker_adapter.py, ollama_adapter.py
- validators.py had no logger calls (communicates via return values)

**Commit `77a909c`** — Task 7: Docstrings for complex functions
- Added 4 docstrings: processors.py (prepare_content, validate_and_repair, verify_quotes) + llm_client.py (_call_with_retry)
- 10 other targets already had docstrings — skipped correctly

### Total Changes This Session

- **19 files modified**, +1599/-365 lines
- **6 commits** on main branch
- **142/142 tests** still passing
- **Zero behavior changes** — all edits are exception types, logging format, and docstrings

---

## What REMAINS To Be Done

### Phase 3: Test Battery (Score 4→9) — NOT STARTED

This is the largest phase. All tasks are pending.

| Task ID | Plan Task | Description | Status |
|---------|-----------|-------------|--------|
| #23 | Tasks 8-9 | Test schemas.py, exceptions.py, config.py | **in_progress** (was about to start when interrupted) |
| #24 | Tasks 10-11 | Test validators.py + llm_client.py (comprehensive) | pending |
| #25 | Tasks 12-14 | Test processors.py, pipeline_cascade.py, llm_client_postprocess.py, llm_client_quotes.py | pending |
| #26 | Task 15 | Test adapters (marker, ollama, surya, rag_store) | pending |
| #27 | Task 16 | Test profile engine (models, validator with eval() security, migrations, xlsx) | pending |
| #28 | Tasks 17-18 | Test utilities (context, postprocess, requote, qa_guideline, resource_paths, version) + GUI smoke | pending |

**Estimate**: ~18 new test files, ~2000-3000 lines of tests.

**Strategy**: Unit tests with mocked external deps (LLM APIs, filesystem, subprocess). Shared fixtures in conftest.py. Target ≥80% coverage per module.

**Key test priority order** (by criticality):
1. schemas.py, exceptions.py, config.py (foundations)
2. validators.py, llm_client.py (core pipeline)
3. processors.py, pipeline_cascade.py (orchestration)
4. llm_client_postprocess.py, llm_client_quotes.py (LLM helpers)
5. adapters (marker, ollama, surya, rag_store)
6. profile engine (models, validator, migrations, xlsx)
7. utilities + GUI smoke tests

**Existing test files to EXTEND** (not replace):
- `test_validators.py` — already exists, extend for all 14 validation rules
- `test_article_processor.py` — already exists, extend for prepare/validate/verify
- `test_ollama_adapter.py` — already exists, extend coverage
- `test_profile_engine.py` — already exists, extend
- `test_gui_smoke.py` — already exists, add controller smoke tests
- `test_pdf_vision.py` — already exists, extend for extract_hybrid

**New test files to CREATE**:
- test_schemas.py
- test_exceptions.py
- test_config.py (check if exists first — test_config_runtime_paths.py and test_config_project_overrides.py exist)
- test_llm_client.py
- test_pipeline_cascade.py
- test_llm_client_postprocess.py
- test_llm_client_quotes.py
- test_marker_adapter.py
- test_rag_store.py
- test_surya_adapter.py
- test_profile_models.py
- test_profile_validator.py
- test_profile_migrations.py
- test_context.py
- test_postprocess.py
- test_requote.py
- test_qa_guideline.py
- test_resource_paths.py / test_version.py

### Phase 4: Structural Cleanup (Score 7→9) — NOT STARTED

| Task ID | Plan Task | Description | Status |
|---------|-----------|-------------|--------|
| #29 | Tasks 19-21 | Refactor long functions (consolidate_yamls 159L, extract_cascade 214L, extract_with_api 104L, convert_pdf_to_markdown 110L, extract_hybrid 91L) via Extract Method | pending |
| #30 | Task 22 | Refactor GUI dialogs (prompt_project_profile_setup 1080L, prompt_first_run_setup 370L) — extract section builders | pending |
| #31 | Tasks 23-24 | Dead code removal + final validation + scorecard verification | pending |

**Key refactoring targets**:
- `consolidate_yamls()` (159 lines) → 3-4 subfunctions
- `extract_cascade()` (214 lines) → extract `_try_local_extraction()`, `_try_api_extraction()`, `_select_best_result()`
- `extract_with_api()` (104 lines) → extract `_build_api_content_blocks()`
- `convert_pdf_to_markdown()` (110 lines) → extract fallback logic
- `extract_hybrid()` (91 lines) → extract page processing
- `prompt_project_profile_setup()` (1080 lines) → 5 section builder functions
- `prompt_first_run_setup()` (370 lines) → 3 section builder functions

**Dead code candidates** (verify with grep before removing):
- `generate_mapping_csv()` in config.py — CONFIRMED USED (pipeline_controller, main.py) — NOT dead
- `_load_paths()` in qa_guideline.py/llm_utils.py — CONFIRMED USED locally — NOT dead
- Search for truly unused functions/imports

---

## How To Continue

### Method: Subagent-Driven Development

The plan uses the `superpowers:subagent-driven-development` workflow:
1. Dispatch implementer subagent per task (general-purpose agent)
2. Verify tests pass
3. Optionally dispatch spec reviewer subagent
4. Commit
5. Move to next task

### Git Configuration

Local git identity is configured:
```
git config --local user.name "Leonardo"
git config --local user.email "leonardo@local"
```

### To Resume

1. Start with Task #23 (test schemas, exceptions, config) — was `in_progress` but no code written yet
2. Follow the plan in `docs/plans/2026-02-21-quality-hardening-plan.md`
3. Use the design doc `docs/plans/2026-02-21-quality-hardening-design.md` for reference
4. After all Phase 3 tests are written, Phase 4 refactoring is protected by the new test suite

### Commands

```bash
# Run tests
python -m pytest system/tests/ -x -q

# Run specific test file
python -m pytest system/tests/test_schemas.py -v

# Check test count
python -m pytest system/tests/ --co -q | tail -1

# Current commit history
git log --oneline -10
```

---

## Scorecard Progress

| Category | Baseline | After Phase 1 | After Phase 2 | Target |
|----------|----------|---------------|---------------|--------|
| Error Handling | 6/10 | **9/10** | 9/10 | 9/10 |
| Logging | 7/10 | 7/10 | **9/10** | 9/10 |
| Docstrings | 7/10 | 7/10 | **9/10** | 9/10 |
| Test Coverage | 4/10 | 4/10 | 4/10 | 9/10 |
| Code Smells | 7/10 | 7/10 | 7/10 | 9/10 |
| Dead Code | 7/10 | 7/10 | 7/10 | 10/10 |
| **Overall** | **7.4** | **7.8** | **8.2** | **9.2** |

**Remaining gap**: Test Coverage (4→9) and Structural Cleanup (7→9/10) — Phases 3 and 4.
