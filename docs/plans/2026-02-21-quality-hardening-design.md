# SAEC Quality Hardening: Error Handling + Logging + Tests + Structural Cleanup

**Date**: 2026-02-21
**Status**: Approved
**Approach**: Horizontal by Category (4 phases)
**Scope**: Full codebase — pipeline core, adapters, profile engine, GUI dialogs
**Baseline**: Score 7.4/10 (142 tests, 0 mypy errors)

## Phase 1: Error Handling Sweep (Score 6→9)

**Goal**: Specify all ~40 generic `except Exception:` blocks across 14 modules.

### Rules

| Current Pattern | Replacement |
|---|---|
| `except Exception:` on imports | `except ImportError:` |
| `except Exception:` on HTTP/API calls | `except (ConnectionError, TimeoutError, httpx.HTTPError):` |
| `except Exception:` on YAML parsing | `except (yaml.YAMLError, ValueError):` |
| `except Exception:` on file I/O | `except (OSError, UnicodeDecodeError):` |
| `except Exception: pass` (silent) | Add `logger.debug(...)` before `pass` |
| `eval()` in validator.py | Document, add security tests, consider `ast.literal_eval` |

### Modules (14)

1. `config.py` (1 block) — import httpx
2. `consolidate.py` (6 blocks) — imports + YAML I/O
3. `context.py` (1 block) — standalone fallback
4. `llm_client.py` (1 block) — API setup warning
5. `llm_client_postprocess.py` (6 blocks) — module loading + profile ops
6. `llm_client_quotes.py` (8 blocks) — quote extraction fallbacks
7. `llm_utils.py` (3 blocks) — YAML postprocessing
8. `pdf_vision.py` (3 blocks) — config loading + TOC
9. `validators.py` (5 blocks) — profile engine loading
10. `qa_guideline.py` (3 blocks) — profile engine ops
11. `adapters/marker_adapter.py` (1 block) — version detection
12. `adapters/ollama_adapter.py` (1 block) — ollama.list()
13. `profile_engine/validator.py` (1 block) — eval() security
14. Various GUI modules — silent catches

**Estimate**: ~40 targeted edits, zero behavior change.

## Phase 2: Logging Hardening + Docstrings (Score 7→9, 7→9)

### 2A. Structured Logging

Adopt `extra=` dict pattern across all pipeline modules:

```python
# Before:
logger.info(f"[{artigo_id}] Extraction with {model}")

# After:
logger.info("Extraction started", extra={"artigo_id": artigo_id, "provider": model, "action": "extract"})
```

**Modules**: `llm_client.py` (8), `marker_adapter.py` (4), `validators.py`, `pipeline_cascade.py`, `processors.py` (5+), `ollama_adapter.py` (6+).

### 2B. Docstrings

Add docstrings only where logic is not self-evident:
- `processors.py`: `prepare_content()`, `validate_and_repair()`, `verify_quotes()`
- `pipeline_cascade.py`: `extract_with_api()`, `_estimate_confidence()`
- `llm_client.py`: `repair_yaml()`, `_call_with_retry()`
- `consolidate.py`: YAML merge functions
- Adapters: conversion methods with complex branching

**Estimate**: ~30 logging edits + ~15 docstrings.

## Phase 3: Test Battery (Score 4→9)

### Strategy

- Unit tests for all 23 untested modules
- Mock external dependencies (LLM APIs, filesystem, subprocess)
- File naming: `test_{module_name}.py`
- Target: ≥80% coverage per module
- Shared fixtures in `conftest.py`

### Tier 1 — Core Pipeline (CRITICAL, 8 modules)

| Module | Lines | Test Focus |
|---|---|---|
| `schemas.py` | 362 | Pydantic validation, defaults, edge cases |
| `validators.py` | 615 | 14 validation rules, malformed YAML, quotes |
| `llm_client.py` | 832 | retry, timeout, provider routing, repair_yaml |
| `processors.py` | 543 | prepare_content, validate_and_repair, pipeline flow |
| `pipeline_cascade.py` | 725 | cascade fallback, confidence, empty content |
| `llm_client_postprocess.py` | 130 | YAML cleanup, fence removal |
| `llm_client_quotes.py` | 305 | quote extraction/validation |
| `config.py` | 789 | LLMConfig validation, path resolution |

### Tier 2 — Adapters (HIGH, 4 modules)

| Module | Lines | Test Focus |
|---|---|---|
| `marker_adapter.py` | 393 | PDF→MD conversion (mock fitz) |
| `ollama_adapter.py` | 694 | model listing, embedding, vision |
| `rag_store.py` | 677 | chunking, search, dedup |
| `surya_adapter.py` | 471 | OCR pipeline (mock surya) |

### Tier 3 — Profile Engine (MEDIUM, 6 modules)

| Module | Lines | Test Focus |
|---|---|---|
| `models.py` | 509 | Profile data models |
| `project_profiles.py` | 615 | Profile building, snapshot |
| `validator.py` | ~200 | Rule evaluation, eval() security |
| `xlsx_profiles.py` | 534 | XLSX import/export |
| `loader.py` | ~150 | Profile loading |
| `migrations.py` | ~100 | Profile version migration |

### Tier 4 — Utilities + GUI (5+ modules)

`context.py`, `exceptions.py`, `export_report.py`, `postprocess.py`, `requote_from_texts.py`, `dialog_profile.py` (smoke), `dialog_setup.py` (smoke)

**Estimate**: ~18 new test files, ~2000-3000 lines of tests.

## Phase 4: Structural Cleanup (Score 7→9, 7→10)

### 4A. Long Functions (>50L) — Extract Method

| Function | File | Lines | Action |
|---|---|---|---|
| `consolidate_yamls()` | consolidate.py | 159 | Extract 3-4 subfunctions |
| `extract_cascade()` | pipeline_cascade.py | 214 | Extract cascade steps |
| `convert_pdf_to_markdown()` | marker_adapter.py | 110 | Extract fallback logic |
| `extract_hybrid()` | pdf_vision.py | 91 | Extract page processing |
| `extract_with_api()` | pipeline_cascade.py | 104 | Extract content building |
| `prompt_project_profile_setup()` | dialog_profile.py | 1080 | Extract section builders |
| `prompt_first_run_setup()` | dialog_setup.py | 370 | Extract section builders |

### 4B. Large Files (>500L)

Evaluate case-by-case:
- `config.py` (789L) — Separate constants from validation if naturally separable
- `llm_client.py` (832L) — Evaluate extracting `repair_yaml` to dedicated module
- Others: Long function reduction (4A) naturally reduces file size

### 4C. Dead Code

Verify and remove (with grep confirmation):
1. `config.py` → `generate_mapping_csv()` — confirm unreferenced
2. `qa_guideline.py` → `_load_paths()` — confirm usage
3. `llm_utils.py` → `_load_paths()` — confirm usage
4. Remaining unused imports

### 4D. Final Cleanup

- Remove unnecessary `# type: ignore` comments
- Format consistency pass
- Verify cross-module delegations are correct

**Estimate**: ~50 refactoring edits + 5-10 dead code removals.

## Success Criteria

| Category | Before | Target |
|---|---|---|
| Error Handling | 6/10 | 9/10 |
| Logging | 7/10 | 9/10 |
| Test Coverage | 4/10 | 9/10 |
| Code Smells | 7/10 | 9/10 |
| Dead Code | 7/10 | 10/10 |
| Docstrings | 7/10 | 9/10 |
| **Overall** | **7.4/10** | **9.2/10** |

All 142+ tests must pass after each phase. Zero mypy errors throughout.

## Testing Strategy

- Run `python -m pytest system/tests/ -x -q` after every batch of changes
- Run `python -m mypy --config-file pyproject.toml system/` after Phases 1-2
- New tests added in Phase 3 become regression guards for Phase 4 refactoring
