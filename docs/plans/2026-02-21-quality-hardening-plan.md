# SAEC Quality Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Raise SAEC codebase quality from 7.4/10 to 9.2/10 across error handling, logging, test coverage, and structural cleanup.

**Architecture:** Four horizontal phases sweep the entire codebase: (1) specify generic exception blocks, (2) add structured logging + docstrings, (3) write unit tests for 23 untested modules, (4) refactor long functions and remove dead code. Each phase improves one quality dimension uniformly across all modules.

**Tech Stack:** Python 3.11+, pytest, unittest.mock, Pydantic v2, PyMuPDF, logging with `extra=` structured fields.

**Design Doc:** `docs/plans/2026-02-21-quality-hardening-design.md`

**Baseline:** 142 tests passing, 0 mypy errors, score 7.4/10.

---

## PHASE 1: Error Handling Sweep (Score 6→9)

Goal: Replace ~40 generic `except Exception:` blocks with specific exception types.

### Task 1: Specify import-related exception blocks

**Files:**
- Modify: `system/src/config.py:293-295`
- Modify: `system/src/consolidate.py:17,28,31,40`
- Modify: `system/src/context.py:13`
- Modify: `system/src/llm_client_postprocess.py:14,26,30`
- Modify: `system/src/llm_client_quotes.py:12,19,26,36,116`
- Modify: `system/src/llm_client_types.py:12,17,22,30`
- Modify: `system/src/llm_utils.py:33,36`
- Modify: `system/src/pdf_vision.py:20,23`
- Modify: `system/src/validators.py:16,28,31`
- Modify: `system/src/qa_guideline.py:46`

**Step 1: Replace all import-fallback `except Exception:` with `except (ImportError, ModuleNotFoundError):`**

Pattern — every block that catches a failed `import` or `importlib.import_module()`:

```python
# Before:
except Exception:  # pragma: no cover - standalone usage

# After:
except (ImportError, ModuleNotFoundError):  # pragma: no cover - standalone usage
```

Apply this transformation to ALL import-related blocks listed above. There are ~22 such blocks.

Special case — `config.py:293`: This imports httpx for timeout calculation:
```python
# Before:
except Exception:
    return self.TIMEOUT_TOTAL

# After:
except (ImportError, ModuleNotFoundError):
    return self.TIMEOUT_TOTAL
```

Special case — `llm_client_types.py:12,17,22`: These set module to None:
```python
# Before:
except Exception:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

# After:
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    httpx = None  # type: ignore[assignment]
```

**Step 2: Run tests**

Run: `python -m pytest system/tests/ -x -q`
Expected: All 142 tests pass (pure exception type change, no behavior change).

**Step 3: Commit**

```bash
git add system/src/config.py system/src/consolidate.py system/src/context.py \
  system/src/llm_client_postprocess.py system/src/llm_client_quotes.py \
  system/src/llm_client_types.py system/src/llm_utils.py system/src/pdf_vision.py \
  system/src/validators.py system/src/qa_guideline.py
git commit -m "refactor: specify ImportError in all import-fallback exception blocks"
```

---

### Task 2: Specify API/network exception blocks in llm_client.py

**Files:**
- Modify: `system/src/llm_client.py:109,426,479,519,578,631,667,743,751,758,787,807`

**Step 1: Define the exception tuple for LLM API calls**

At the top of `llm_client.py`, after imports, add:

```python
# Exception types for LLM API calls — used in except clauses
_LLM_API_ERRORS: tuple[type[Exception], ...] = (ConnectionError, TimeoutError, OSError)
try:
    import httpx
    _LLM_API_ERRORS = (*_LLM_API_ERRORS, httpx.HTTPError, httpx.TimeoutException)
except (ImportError, ModuleNotFoundError):
    pass
try:
    from anthropic import APIError as AnthropicAPIError, APIConnectionError as AnthropicConnError
    _LLM_API_ERRORS = (*_LLM_API_ERRORS, AnthropicAPIError, AnthropicConnError)
except (ImportError, ModuleNotFoundError):
    pass
try:
    from openai import OpenAIError
    _LLM_API_ERRORS = (*_LLM_API_ERRORS, OpenAIError)
except (ImportError, ModuleNotFoundError):
    pass
```

**Step 2: Replace generic catches in provider-specific methods**

For lines 426, 479, 519, 578, 631, 667 (individual provider methods):
```python
# Before:
except Exception as e:
    logger.error(f"Anthropic API error: {e}")

# After:
except _LLM_API_ERRORS as e:
    logger.error(f"Anthropic API error: {e}")
```

For lines 787, 807 (repair methods):
```python
# Before:
except Exception as e:
    raise LLMError(str(e), provider="openai", retriable=True)

# After:
except _LLM_API_ERRORS as e:
    raise LLMError(str(e), provider="openai", retriable=True)
```

For line 109 (general call wrapper) and 743, 751, 758 (repair fallback chain): Keep `except Exception as e:` — these are intentional catch-all with re-raise/logging. Add a comment:
```python
except Exception as e:  # Intentional: catch-all for retry/fallback logic
```

**Step 3: Run tests**

Run: `python -m pytest system/tests/ -x -q`
Expected: All 142 tests pass.

**Step 4: Commit**

```bash
git add system/src/llm_client.py
git commit -m "refactor: specify LLM API exception types in llm_client.py"
```

---

### Task 3: Specify remaining exception blocks

**Files:**
- Modify: `system/src/consolidate.py:156,162,241,282`
- Modify: `system/src/llm_client_postprocess.py:81,149,154,161`
- Modify: `system/src/llm_client_quotes.py:128,152,253`
- Modify: `system/src/llm_utils.py:45`
- Modify: `system/src/pdf_vision.py:79,153`
- Modify: `system/src/adapters/marker_adapter.py:129,246,332,374`
- Modify: `system/src/profile_engine/validator.py:218`

**Step 1: Specify by category**

**YAML/data processing** (`consolidate.py:241,282`, `llm_client_quotes.py:128`, `llm_utils.py:45`):
```python
# Before:
except Exception as e:

# After:
except (yaml.YAMLError, ValueError, KeyError, TypeError) as e:
```

**Profile engine calls** (`consolidate.py:156,162`, `llm_client_postprocess.py:149,154,161`):
```python
# Before:
except Exception:
    return []  # or return True / return None

# After:
except (ImportError, ModuleNotFoundError, AttributeError, OSError):
```

**Ollama formatting** (`llm_client_postprocess.py:81`):
```python
# Before:
except Exception as e:
    logger.warning("Falha ao formatar YAML via Ollama: %s", e)

# After:
except (ConnectionError, TimeoutError, OSError, ValueError) as e:
    logger.warning("Falha ao formatar YAML via Ollama: %s", e)
```

**Quote requote attempts** (`llm_client_quotes.py:152,253`):
```python
# Before:
except Exception:
    if provider != fallback_provider:

# After:
except (ConnectionError, TimeoutError, OSError, ValueError) as e:
    logger.debug("Requote attempt failed: %s", e)
    if provider != fallback_provider:
```

**PDF/image analysis** (`pdf_vision.py:79,153`):
```python
# Before:
except Exception:
    return None

# After:
except (OSError, ValueError, RuntimeError):
    return None
```

**Marker adapter** (`marker_adapter.py:129`):
```python
# Before:
except Exception:
    pass

# After:
except (AttributeError, ImportError, TypeError):
    pass
```

For `marker_adapter.py:246,332,374` — these catch broad PDF processing errors. Keep as `except Exception as e:` but add comment:
```python
except Exception as e:  # Broad: PDF libraries raise diverse error types
```

**Eval safety** (`profile_engine/validator.py:218`) — keep `except Exception:` but add comment:
```python
except Exception:  # Intentional: eval() can raise any exception type
    return False
```

**Step 2: Run tests**

Run: `python -m pytest system/tests/ -x -q`
Expected: All 142 tests pass.

**Step 3: Commit**

```bash
git add system/src/consolidate.py system/src/llm_client_postprocess.py \
  system/src/llm_client_quotes.py system/src/llm_utils.py system/src/pdf_vision.py \
  system/src/adapters/marker_adapter.py system/src/profile_engine/validator.py
git commit -m "refactor: specify exception types in data processing and adapter blocks"
```

---

### Task 4: Run full validation after Phase 1

**Step 1: Run full test suite**

Run: `python -m pytest system/tests/ -v`
Expected: All 142 tests pass.

**Step 2: Commit phase marker**

No code change — just verify clean state.

---

## PHASE 2: Logging Hardening + Docstrings (Score 7→9)

### Task 5: Add structured logging to llm_client.py

**Files:**
- Modify: `system/src/llm_client.py`

**Step 1: Update log calls to use `extra=` dict**

Find all `logger.info/warning/error` calls and add structured `extra=` fields. Pattern:

```python
# Before:
logger.info(f"Calling {provider} for extraction")

# After:
logger.info(
    "LLM extraction call",
    extra={"provider": provider, "action": "extract", "artigo_id": artigo_id},
)
```

Apply to all ~8 log calls in the file. Key fields:
- `provider`: the LLM provider name
- `action`: one of "extract", "repair", "vision", "retry"
- `artigo_id`: article ID when available (else omit)
- `model`: model name when available

**Step 2: Run tests**

Run: `python -m pytest system/tests/ -x -q`
Expected: All tests pass (log message changes don't affect behavior).

**Step 3: Commit**

```bash
git add system/src/llm_client.py
git commit -m "refactor: add structured logging fields to llm_client.py"
```

---

### Task 6: Add structured logging to pipeline and adapters

**Files:**
- Modify: `system/src/pipeline_cascade.py`
- Modify: `system/src/processors.py`
- Modify: `system/src/adapters/marker_adapter.py`
- Modify: `system/src/adapters/ollama_adapter.py`
- Modify: `system/src/validators.py`

**Step 1: Update log calls in each module**

Same pattern as Task 5. Each module's key fields:

- `pipeline_cascade.py`: `artigo_id`, `provider`, `model`, `action` (cascade_step, fallback, confidence)
- `processors.py`: `artigo_id`, `action` (prepare, validate, repair, verify_quotes)
- `marker_adapter.py`: `artigo_id`, `action` (convert, analyze, stats)
- `ollama_adapter.py`: `model`, `action` (list, embed, vision, generate)
- `validators.py`: `artigo_id`, `action` (validate), `rule` (which validation rule)

**Step 2: Run tests**

Run: `python -m pytest system/tests/ -x -q`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add system/src/pipeline_cascade.py system/src/processors.py \
  system/src/adapters/marker_adapter.py system/src/adapters/ollama_adapter.py \
  system/src/validators.py
git commit -m "refactor: add structured logging to pipeline, adapters, and validators"
```

---

### Task 7: Add docstrings to complex public functions

**Files:**
- Modify: `system/src/processors.py`
- Modify: `system/src/pipeline_cascade.py`
- Modify: `system/src/llm_client.py`
- Modify: `system/src/consolidate.py`

**Step 1: Add docstrings**

Only where logic is not self-evident. Keep concise (1-3 lines). Examples:

```python
# processors.py
def prepare_content(self, artigo_id: str, ...) -> ContentBundle:
    """Build LLM input from hybrid content, selecting text vs vision based on page quality scores."""

def validate_and_repair(self, artigo_id: str, yaml_text: str, ...) -> tuple[str, ValidationResult]:
    """Validate YAML against schema and profile rules; attempt LLM repair up to max_retries on failure."""

def verify_quotes(self, artigo_id: str, yaml_text: str, texts: dict) -> str:
    """Cross-check extracted quotes against source text, flagging or correcting mismatches."""
```

```python
# pipeline_cascade.py
def extract_with_api(artigo_id: str, ...) -> CascadeResult:
    """Run CIMO extraction via cloud API with vision support, building multimodal content blocks."""

def _estimate_confidence(yaml_text: str) -> float:
    """Score extraction quality 0.0-1.0 based on presence of key CIMO fields and quote count."""
```

```python
# llm_client.py
def repair_yaml(self, broken_yaml: str, ...) -> str:
    """Attempt to fix malformed YAML via LLM, trying Ollama models first, then cloud providers."""
```

**Step 2: Run tests**

Run: `python -m pytest system/tests/ -x -q`
Expected: All tests pass.

**Step 3: Commit**

```bash
git add system/src/processors.py system/src/pipeline_cascade.py \
  system/src/llm_client.py system/src/consolidate.py
git commit -m "docs: add docstrings to complex public functions"
```

---

## PHASE 3: Test Battery (Score 4→9)

Strategy: Write unit tests for all untested modules, grouped by tier. Each task creates 2-4 test files for related modules.

### Task 8: Test schemas.py and exceptions.py

**Files:**
- Create: `system/tests/test_schemas.py`
- Create: `system/tests/test_exceptions.py`

**Step 1: Write test_schemas.py**

Test Pydantic models: valid construction, defaults, validation errors, edge cases.

```python
"""Tests for SAEC Pydantic data models."""
from __future__ import annotations
import pytest
from schemas import (
    # Import all public models — exact names from schemas.py
)

class TestArtigoModel:
    def test_valid_construction(self): ...
    def test_missing_required_field_raises(self): ...
    def test_default_values(self): ...
    def test_empty_quotes_list(self): ...

class TestExtractionResult:
    def test_valid_result(self): ...
    def test_confidence_range(self): ...
```

**Step 2: Write test_exceptions.py**

```python
"""Tests for SAEC exception hierarchy."""
from __future__ import annotations
from exceptions import IngestError, ExtractError, ValidationError, LLMError

def test_ingest_error_is_exception(): ...
def test_llm_error_has_provider_and_retriable(): ...
def test_exception_hierarchy(): ...
```

**Step 3: Run tests**

Run: `python -m pytest system/tests/test_schemas.py system/tests/test_exceptions.py -v`
Expected: All new tests pass.

**Step 4: Commit**

```bash
git add system/tests/test_schemas.py system/tests/test_exceptions.py
git commit -m "test: add unit tests for schemas.py and exceptions.py"
```

---

### Task 9: Test config.py

**Files:**
- Create: `system/tests/test_config.py`

**Step 1: Write tests for LLMConfig, Paths, and validation logic**

```python
"""Tests for SAEC configuration module."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
import pytest
from config import LLMConfig, Paths, ExtractionConfig

class TestLLMConfig:
    def test_default_values(self): ...
    def test_timeout_values(self): ...
    def test_provider_detection(self): ...

class TestPaths:
    def test_path_resolution(self, tmp_path): ...
    def test_ensure_dirs_creates_directories(self, tmp_path): ...

class TestExtractionConfig:
    def test_default_dpi(self): ...
    def test_force_hybrid_flag(self): ...
```

**Step 2: Run and commit**

Run: `python -m pytest system/tests/test_config.py -v`

```bash
git add system/tests/test_config.py
git commit -m "test: add unit tests for config.py"
```

---

### Task 10: Test validators.py (comprehensive)

**Files:**
- Create or extend: `system/tests/test_validators.py` (already exists — extend it)

**Step 1: Read existing test_validators.py to understand current coverage**

Check what's already tested. Add missing tests for:
- All 14 validation rules
- Malformed YAML handling
- Quote validation edge cases
- Profile-aware validation (mock profile engine)

**Step 2: Add missing test cases**

Focus on untested validation rules and edge cases. Use fixtures from conftest.py.

**Step 3: Run and commit**

Run: `python -m pytest system/tests/test_validators.py -v`

```bash
git add system/tests/test_validators.py
git commit -m "test: expand validator test coverage to all 14 rules"
```

---

### Task 11: Test llm_client.py core logic

**Files:**
- Create: `system/tests/test_llm_client.py`

**Step 1: Write tests with mocked providers**

```python
"""Tests for SAEC LLM client."""
from __future__ import annotations
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from llm_client import LLMClient
from exceptions import LLMError

class TestLLMClientInit:
    def test_creates_with_config(self): ...
    def test_no_providers_warns(self): ...

class TestExtraction:
    @patch("llm_client.LLMClient._call_anthropic")
    def test_extract_with_anthropic(self, mock_call): ...

    @patch("llm_client.LLMClient._call_openai_client")
    def test_extract_with_openai(self, mock_call): ...

class TestRepairYaml:
    @patch("llm_client.LLMClient._repair_openai")
    def test_repair_tries_ollama_first(self, mock_repair): ...

    def test_repair_raises_on_all_failures(self): ...

class TestRetry:
    def test_retry_on_transient_error(self): ...
    def test_no_retry_on_fatal_error(self): ...
```

**Step 2: Run and commit**

Run: `python -m pytest system/tests/test_llm_client.py -v`

```bash
git add system/tests/test_llm_client.py
git commit -m "test: add unit tests for llm_client.py with mocked providers"
```

---

### Task 12: Test processors.py

**Files:**
- Extend: `system/tests/test_article_processor.py` (already exists)

**Step 1: Read existing test file, add missing coverage**

Focus on: `prepare_content()`, `validate_and_repair()`, `verify_quotes()` — the 3 complex methods identified in docstring phase.

**Step 2: Run and commit**

```bash
git add system/tests/test_article_processor.py
git commit -m "test: expand article processor tests for prepare/validate/verify"
```

---

### Task 13: Test pipeline_cascade.py

**Files:**
- Create: `system/tests/test_pipeline_cascade.py`

**Step 1: Write tests for cascade logic**

```python
"""Tests for multi-model cascade extraction pipeline."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest

class TestEstimateConfidence:
    def test_high_confidence_with_all_fields(self): ...
    def test_low_confidence_with_missing_fields(self): ...
    def test_zero_confidence_empty_yaml(self): ...

class TestExtractCascade:
    @patch("pipeline_cascade.extract_with_local")
    @patch("pipeline_cascade.extract_with_api")
    def test_local_first_then_api_fallback(self, mock_api, mock_local): ...

    def test_returns_best_result_by_confidence(self): ...

class TestExtractWithApi:
    def test_builds_content_blocks_from_text(self): ...
    def test_handles_empty_images(self): ...
```

**Step 2: Run and commit**

```bash
git add system/tests/test_pipeline_cascade.py
git commit -m "test: add unit tests for pipeline_cascade.py"
```

---

### Task 14: Test llm_client_postprocess.py and llm_client_quotes.py

**Files:**
- Create: `system/tests/test_llm_client_postprocess.py`
- Create: `system/tests/test_llm_client_quotes.py`

**Step 1: Write tests for YAML postprocessing**

```python
"""Tests for LLM response postprocessing."""
def test_removes_markdown_fences(): ...
def test_preserves_valid_yaml(): ...
def test_handles_empty_response(): ...
```

**Step 2: Write tests for quote extraction**

```python
"""Tests for quote extraction and validation."""
def test_extract_quotes_from_yaml(): ...
def test_validate_quote_against_source(): ...
def test_fuzzy_match_threshold(): ...
```

**Step 3: Run and commit**

```bash
git add system/tests/test_llm_client_postprocess.py system/tests/test_llm_client_quotes.py
git commit -m "test: add tests for LLM postprocessing and quote extraction"
```

---

### Task 15: Test adapters (marker, ollama, surya, rag_store)

**Files:**
- Extend: `system/tests/test_ollama_adapter.py` (already exists)
- Create: `system/tests/test_marker_adapter.py`
- Create: `system/tests/test_rag_store.py`
- Create: `system/tests/test_surya_adapter.py`

**Step 1: Read existing ollama test, extend coverage**

**Step 2: Write marker adapter tests (mock fitz/PyMuPDF)**

```python
"""Tests for Marker PDF adapter."""
from unittest.mock import patch, MagicMock

class TestConvertPdfToMarkdown:
    @patch("marker_adapter.fitz")
    def test_converts_valid_pdf(self, mock_fitz): ...
    def test_raises_on_missing_file(self): ...

class TestAnalyzePdf:
    @patch("marker_adapter.fitz")
    def test_extracts_page_count(self, mock_fitz): ...
```

**Step 3: Write RAG store tests**

```python
"""Tests for RAG vector store."""
class TestChunking:
    def test_chunks_text_by_size(self): ...
    def test_dedup_removes_near_duplicates(self): ...

class TestSearch:
    def test_search_returns_ranked_results(self): ...
```

**Step 4: Write Surya adapter tests (mock surya)**

```python
"""Tests for Surya OCR adapter."""
class TestOcrPipeline:
    @patch("surya_adapter.surya")
    def test_ocr_returns_text(self, mock_surya): ...
```

**Step 5: Run and commit**

Run: `python -m pytest system/tests/test_marker_adapter.py system/tests/test_rag_store.py system/tests/test_surya_adapter.py system/tests/test_ollama_adapter.py -v`

```bash
git add system/tests/test_marker_adapter.py system/tests/test_rag_store.py \
  system/tests/test_surya_adapter.py system/tests/test_ollama_adapter.py
git commit -m "test: add unit tests for all adapters"
```

---

### Task 16: Test profile engine modules

**Files:**
- Extend: `system/tests/test_profile_engine.py` (already exists)
- Create: `system/tests/test_profile_models.py`
- Create: `system/tests/test_profile_validator.py`
- Create: `system/tests/test_profile_migrations.py`

**Step 1: Read existing profile tests, identify gaps**

**Step 2: Write model tests**

```python
"""Tests for profile data models."""
class TestProfileModel:
    def test_valid_construction(self): ...
    def test_field_defaults(self): ...
```

**Step 3: Write validator tests (including eval() security)**

```python
"""Tests for profile rule evaluation."""
class TestEvaluateRuleExpr:
    def test_simple_equality(self): ...
    def test_rejects_dangerous_input(self): ...
    def test_returns_false_on_eval_error(self): ...

class TestAssertSafeAst:
    def test_allows_comparisons(self): ...
    def test_rejects_function_calls(self): ...
    def test_rejects_import_expressions(self): ...
```

**Step 4: Write migration tests**

```python
"""Tests for profile version migrations."""
def test_migration_from_v1_to_v2(): ...
def test_no_migration_needed_for_current(): ...
```

**Step 5: Run and commit**

```bash
git add system/tests/test_profile_models.py system/tests/test_profile_validator.py \
  system/tests/test_profile_migrations.py system/tests/test_profile_engine.py
git commit -m "test: add comprehensive profile engine tests including eval security"
```

---

### Task 17: Test utility modules

**Files:**
- Create: `system/tests/test_context.py`
- Create: `system/tests/test_postprocess.py`
- Create: `system/tests/test_requote.py`
- Create: `system/tests/test_qa_guideline.py`

**Step 1: Write context tests**

```python
"""Tests for AppContext DI container."""
def test_creates_with_paths(self): ...
def test_provides_llm_client(self): ...
```

**Step 2: Write postprocess tests**

```python
"""Tests for YAML postprocessing."""
def test_apply_postprocess_rules(): ...
def test_handles_empty_input(): ...
```

**Step 3: Write requote tests**

```python
"""Tests for requote-from-texts logic."""
def test_requote_finds_better_match(): ...
def test_requote_preserves_valid_quote(): ...
```

**Step 4: Write QA guideline tests**

```python
"""Tests for QA guideline evaluation."""
def test_evaluate_guideline_rules(): ...
def test_handles_missing_profile(): ...
```

**Step 5: Run and commit**

```bash
git add system/tests/test_context.py system/tests/test_postprocess.py \
  system/tests/test_requote.py system/tests/test_qa_guideline.py
git commit -m "test: add tests for context, postprocess, requote, and QA guideline"
```

---

### Task 18: Test remaining modules + GUI smoke tests

**Files:**
- Create: `system/tests/test_resource_paths.py`
- Create: `system/tests/test_version.py`
- Create: `system/tests/test_pdf_vision_extended.py`
- Extend: `system/tests/test_gui_smoke.py` (add smoke tests for new controllers)

**Step 1: Write resource_paths and version tests**

```python
"""Tests for resource path resolution."""
def test_get_resource_path_returns_path(): ...
def test_handles_frozen_app(): ...
```

```python
"""Tests for version module."""
def test_version_is_string(): ...
```

**Step 2: Extend pdf_vision tests**

Read existing `test_pdf_vision.py`, add coverage for `extract_hybrid()`, `_has_significant_images()`.

**Step 3: Extend GUI smoke tests**

Verify new controllers import cleanly:
```python
def test_session_manager_importable(): ...
def test_pipeline_controller_importable(): ...
def test_project_manager_importable(): ...
def test_queue_controller_importable(): ...
```

**Step 4: Run full suite and commit**

Run: `python -m pytest system/tests/ -v --tb=short`
Expected: All tests pass (142 original + all new).

```bash
git add system/tests/
git commit -m "test: complete test battery — all modules covered"
```

---

## PHASE 4: Structural Cleanup (Score 7→9)

### Task 19: Refactor consolidate_yamls() — Extract Method

**Files:**
- Modify: `system/src/consolidate.py`

**Step 1: Identify extractable subfunctions in `consolidate_yamls()` (159 lines)**

Read the function and identify 3-4 logical sections:
- YAML file discovery and loading
- Row flattening and validation
- CSV/report writing
- Error aggregation

**Step 2: Extract each section into a named helper function**

Keep the main function as an orchestrator calling the helpers. Each helper should be ≤40 lines.

**Step 3: Run tests**

Run: `python -m pytest system/tests/test_consolidate.py -v`
Expected: All consolidate tests still pass.

**Step 4: Commit**

```bash
git add system/src/consolidate.py
git commit -m "refactor: extract subfunctions from consolidate_yamls()"
```

---

### Task 20: Refactor pipeline_cascade.py long functions

**Files:**
- Modify: `system/src/pipeline_cascade.py`

**Step 1: Refactor `extract_cascade()` (214 lines)**

Extract:
- `_try_local_extraction()` — local model attempt
- `_try_api_extraction()` — API fallback attempt
- `_select_best_result()` — confidence comparison

**Step 2: Refactor `extract_with_api()` (104 lines)**

Extract:
- `_build_api_content_blocks()` — content assembly for API call

**Step 3: Run tests**

Run: `python -m pytest system/tests/test_pipeline_cascade.py -v`

**Step 4: Commit**

```bash
git add system/src/pipeline_cascade.py
git commit -m "refactor: extract subfunctions from cascade long functions"
```

---

### Task 21: Refactor marker_adapter.py and pdf_vision.py

**Files:**
- Modify: `system/src/adapters/marker_adapter.py`
- Modify: `system/src/pdf_vision.py`

**Step 1: Refactor `convert_pdf_to_markdown()` (110 lines) in marker_adapter.py**

Extract fallback/retry logic into a helper.

**Step 2: Refactor `extract_hybrid()` (91 lines) in pdf_vision.py**

Extract page processing loop into `_process_page()` helper.

**Step 3: Run tests**

Run: `python -m pytest system/tests/test_marker_adapter.py system/tests/test_pdf_vision.py -v`

**Step 4: Commit**

```bash
git add system/src/adapters/marker_adapter.py system/src/pdf_vision.py
git commit -m "refactor: extract subfunctions from marker and pdf_vision"
```

---

### Task 22: Refactor GUI dialog long functions

**Files:**
- Modify: `system/src/gui/dialog_profile.py`
- Modify: `system/src/gui/dialog_setup.py`

**Step 1: Refactor `prompt_project_profile_setup()` (1080 lines)**

Extract section builders:
- `_build_general_section()` — general profile options
- `_build_cimo_section()` — CIMO-specific fields
- `_build_custom_spec_section()` — custom spec builder
- `_build_validation_section()` — validation rule config
- `_build_preview_section()` — preview/summary

Keep the main function as orchestrator wiring sections into the dialog.

**Step 2: Refactor `prompt_first_run_setup()` (370 lines)**

Extract:
- `_build_welcome_section()`
- `_build_provider_section()`
- `_build_workspace_section()`

**Step 3: Run GUI smoke tests**

Run: `python -m pytest system/tests/test_gui_smoke.py -v`

**Step 4: Commit**

```bash
git add system/src/gui/dialog_profile.py system/src/gui/dialog_setup.py
git commit -m "refactor: extract section builders from dialog long functions"
```

---

### Task 23: Remove dead code and clean up

**Files:**
- Possibly modify: `system/src/config.py` (if `generate_mapping_csv` can be moved)
- Possibly modify: various files (unused imports)

**Step 1: Verify dead code candidates with grep**

For each candidate, run grep across the entire system/ folder:
```bash
grep -r "generate_mapping_csv" system/
grep -r "_load_paths" system/src/qa_guideline.py system/src/llm_utils.py
```

Based on exploration results:
- `generate_mapping_csv`: USED (in pipeline_controller.py, main.py, test_mapping_sync.py) — NOT dead code
- `_load_paths`: USED locally in each module — NOT dead code

**Step 2: Search for truly unused functions/imports**

Run a targeted search for functions defined but never called outside their file.

**Step 3: Remove confirmed dead code and unused imports**

**Step 4: Run full test suite**

Run: `python -m pytest system/tests/ -v --tb=short`

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove dead code and unused imports"
```

---

### Task 24: Final validation

**Step 1: Run full test suite**

Run: `python -m pytest system/tests/ -v`
Expected: ALL tests pass (original 142 + all new tests).

**Step 2: Verify scorecard improvement**

| Category | Before | After | Target |
|---|---|---|---|
| Error Handling | 6/10 | 9/10 | 9/10 |
| Logging | 7/10 | 9/10 | 9/10 |
| Test Coverage | 4/10 | 9/10 | 9/10 |
| Code Smells | 7/10 | 9/10 | 9/10 |
| Dead Code | 7/10 | 10/10 | 10/10 |
| Docstrings | 7/10 | 9/10 | 9/10 |
| **Overall** | **7.4/10** | **9.2/10** | **9.2/10** |

**Step 3: Final commit**

```bash
git add docs/plans/2026-02-21-quality-hardening-design.md \
  docs/plans/2026-02-21-quality-hardening-plan.md
git commit -m "docs: add quality hardening design and implementation plan"
```
