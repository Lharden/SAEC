---
name: validate-batch
description: Validate all extracted YAML files and produce a quality summary report
disable-model-invocation: true
---

# Validate Batch

Run CIMO validation on all (or specific) YAML outputs and produce a quality summary.

## Usage

- `/validate-batch` - Validate all YAMLs in Extraction/outputs/yamls/
- `/validate-batch ART_001 ART_002` - Validate specific articles only
- `/validate-batch --failing` - Show only failing validations

## Steps

1. **Discover YAMLs**: Glob all `*.yaml` files in the YAML output directory
2. **Load validator**: Import `YAMLValidator` from `system/src/validators.py`
3. **Validate each file**:
   - Parse YAML content
   - Run all 14 validation rules
   - Collect ValidationResult per file
4. **Produce summary table**:

```markdown
| Article | Status | Errors | Warnings | Details |
|---------|--------|--------|----------|---------|
| ART_001 | PASS   | 0      | 1        | warn: short_outcome |
| ART_002 | FAIL   | 2      | 0        | err: missing_context, invalid_quotes |
```

5. **Show statistics**:
   - Total files, pass count, fail count, pass rate
   - Most common error types
   - Articles needing attention (sorted by error count)

## Validation Rules Reference

The validator checks for:
- Required CIMO fields present and non-empty
- Quote format validity (proper citation marks)
- Risk type classification correctness
- Field length minimums and maximums
- Cross-field consistency
- YAML structure compliance

## Implementation

```python
# Core logic to execute
import sys
sys.path.insert(0, "system/src")
from validators import YAMLValidator
from pathlib import Path
import yaml

validator = YAMLValidator()
yamls_dir = Path("Extraction/outputs/yamls")

results = []
for yaml_file in sorted(yamls_dir.glob("*.yaml")):
    content = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
    result = validator.validate(content)
    results.append((yaml_file.stem, result))
```

## Output Format

After validation, present results as:
1. A markdown summary table (pass/fail per article)
2. Aggregate statistics (pass rate, common errors)
3. Actionable recommendations for failing articles
