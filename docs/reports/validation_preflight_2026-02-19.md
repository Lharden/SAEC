# Pre-Validation Technical Report (No Paid API Usage)

Date: 2026-02-19  
Workspace: `00 Dados RSL`  
Scope: technical pre-validation before final validation run, without consuming cloud paid tokens.

## Validation constraints

- Cloud API keys were forced to placeholders during execution:
  - `OPENAI_API_KEY=your-cloud-provider-2-key-here`
  - `ANTHROPIC_API_KEY=your-cloud-provider-1-key-here`
- Tests and pipeline checks were run in local/dry-run mode only.
- No extraction run was executed against paid cloud providers.

## Executed checks

### 1) Automated test suite (primary gate)

Command:

```powershell
.\.venv\Scripts\python -m pytest system/tests -q --basetemp=.runtime/pytest_gateA -o cache_dir=.runtime/pytest_cache_gateA
```

Result:

- `142 passed in 29.87s`

Additional wrapper verification:

```powershell
powershell -File system/run_tests.ps1 system/tests -q
```

Result:

- `142 passed in 31.46s`

### 2) Pipeline smoke checks (no token usage)

Commands and outcomes:

```powershell
.\.venv\Scripts\python system/main.py --step 1
```

- Exit code `0` (configuration/bootstrap OK).

```powershell
.\.venv\Scripts\python system/main.py --step 2 --article ART_001 --dry-run
```

- Exit code `0` (ingestion dry-run path OK).

```powershell
.\.venv\Scripts\python system/main.py --step 3 --dry-run
```

- Exit code `0` (`Nenhum artigo para extrair`, expected with no ingest outputs).

```powershell
.\.venv\Scripts\python system/main.py --step 3 --article ART_001 --dry-run
```

- Exit code `1` (`Artigo ... não encontrado, sem ingestão...`), expected precondition behavior.

```powershell
.\.venv\Scripts\python system/main.py --step 5
```

- Exit code `1` (`Nenhum YAML para consolidar`), expected because no YAML outputs exist.

```powershell
.\.venv\Scripts\python system/main.py --all --dry-run
```

- Step 1/2/3 flows executed and printed as finalized.
- Process exit code `1` because final status depends on consolidation success (no YAML available).

### 3) Static analysis

Tooling availability:

- `ruff`: not installed in current venv (`No module named ruff`).
- `pyright`: installed (`1.1.408`).
- `mypy`: installed (`1.19.1`).

Commands:

```powershell
.\.venv\Scripts\python -m pyright system/src system/main.py
.\.venv\Scripts\python -m mypy system/src system/main.py
```

Results:

- Pyright: `39 errors, 15 warnings`
- Mypy: `105 errors in 18 files`

Raw logs saved:

- `.runtime/pyright_validation.txt`
- `.runtime/mypy_validation.txt`

## Gate status (go/no-go)

- Gate A (automated tests): **PASS**
- Gate B (pipeline dry-run smoke): **PASS with expected precondition failures**
- Gate C (no paid API usage): **PASS**
- Gate D (strict static typing): **FAIL (informational/non-blocking for current runtime validation)**

## Findings (prioritized)

### P1

1. `system/run_tests.ps1` can collect repository root when called with options only (for example `-q`), which may trigger permission errors in root cache-like directories.
   - Reproduced previously with: `powershell -File system/run_tests.ps1 -q`
   - Stable workaround: pass explicit target `system/tests`.

### P2

1. `--all --dry-run` returns non-zero when no YAMLs exist because consolidation is strict in exit-code computation.
   - Behavior is coherent with current logic, but can look like a failure after successful dry-run bootstrap.
2. Static typing debt remains high (pyright/mypy), although runtime tests are green.

## Final recommendation for the final validation run

Proceed with the final validation run under these conditions:

1. Use explicit test target in wrapper commands (`system/tests`).
2. Ensure ingest/extract outputs exist before treating step 5 result as a hard failure.
3. Keep cloud API keys as placeholders unless intentionally enabling paid providers.

