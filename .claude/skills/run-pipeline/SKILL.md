---
name: run-pipeline
description: Run the SAEC extraction pipeline on specific articles or all pending articles
disable-model-invocation: true
---

# Run Pipeline

Execute the SAEC CIMO extraction pipeline on one or more articles.

## Usage

- `/run-pipeline ART_001` - Process a specific article
- `/run-pipeline ART_001 --force` - Force reprocessing even if YAML exists
- `/run-pipeline --all` - Process all pending articles
- `/run-pipeline --dry-run` - Simulate without executing
- `/run-pipeline --step 2 ART_001` - Run only ingest step for an article

## Steps

1. **Parse arguments**: Extract article ID, flags (--force, --dry-run, --step)
2. **Validate article exists**: Check `Extraction/mapping.csv` for the article ID
3. **Check prerequisites**:
   - For ingest (step 2): PDF must exist in articles folder
   - For extract (step 3): `hybrid.json` must exist (run ingest first if missing)
   - For consolidate (step 5): YAMLs must exist
4. **Execute pipeline**:
   - Single article: `python system/main.py --article <ID> --step <N>`
   - All articles: `python system/main.py --all`
   - With force: append `--force`
   - Dry run: append `--dry-run`
5. **Report results**:
   - If extraction succeeded: read and summarize the output YAML
   - If validation failed: show which CIMO fields had issues
   - If errors occurred: show error details and suggest fixes

## Pipeline Steps Reference

| Step | Command | What It Does |
|------|---------|--------------|
| 1 | `--step 1` | Configuration check (dependencies, paths, APIs) |
| 2 | `--step 2` | PDF ingest (text + images extraction) |
| 3 | `--step 3` | LLM extraction (CIMO data from hybrid content) |
| 5 | `--step 5` | Consolidation (YAMLs to Excel) |
| all | `--all` | Full pipeline (1 -> 2 -> 3 -> 5) |

## Example Interaction

```
User: /run-pipeline ART_042

Claude:
1. Checking mapping... ART_042 found (PDF: smith_2024_scm_ai.pdf)
2. Checking ingest... hybrid.json exists (cached)
3. Running extraction...
   $ python system/main.py --step 3 --article ART_042
4. Results: ART_042.yaml created successfully
   - Context: Oil & Gas supply chain in offshore Brazil
   - Intervention: ML-based demand forecasting
   - Mechanism: Reduces bullwhip effect via predictions
   - Outcome: 15% inventory cost reduction
```
