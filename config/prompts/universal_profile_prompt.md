# Universal Profile Extraction Prompt

Objective:
Extract structured evidence from the article and return ONLY valid YAML according to the active project profile.

Mandatory rules:
- Return YAML only (no preface, no explanations outside YAML).
- Use only field names declared in the active profile.
- Preserve exact field names and expected structure.
- Do not fabricate values. If evidence is missing, use `NR` or empty value according to field rules.
- Keep cross-field consistency (context, intervention, mechanism, outcomes must not conflict).
- When quotes are required, use literal excerpts and include page/section when available.
- If inference is allowed by the profile, clearly separate inferred content from declared evidence.

Output quality checklist:
- YAML parses without errors.
- All required fields are present.
- Enum/regex/length constraints are respected.
- Business rules in the active profile are respected.
- Quotes policy (count, schema, types) is respected.

Final instruction:
Return the final YAML only.

