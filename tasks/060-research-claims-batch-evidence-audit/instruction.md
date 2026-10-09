Task: Batch Research Claims Evidence Audit

Use only the offline materials in `$WORKSPACE`.

Inputs:
- `$WORKSPACE/claims/claims.csv`
- `$WORKSPACE/sources/*`

Audit every claim and create:

1. `$WORKSPACE/claim_audit.csv`
   - Header exactly:
     `claim_id,claim_text,status,primary_source,evidence_location,evidence_signal,secondary_sources,rationale`
   - `status` must be exactly one of:
     `supported`, `contradicted`, `overstated`, `unsupported`, `not_reproducible`
   - Include exactly one row per claim.
   - For numeric claims, identify the source row, metric, cohort, field, or section used.
   - For multi-source claims, list secondary sources separated by semicolons.

2. `$WORKSPACE/evidence_matrix.json`
   - Top level object with key `claims`.
   - Each item must include `claim_id`, `status`, `evidence`, and `reproducibility_note`.
   - `evidence` may be either one evidence object or a non-empty array of
     evidence objects.
   - Each evidence item must include `source_file`, `location`, `supports_or_refutes`, and `signal`.
   - Preferred `supports_or_refutes` values are `supports` for supported
     claims, `refutes` for contradicted claims, `limits` for overstated claims,
     `insufficient` for unsupported claims, and `reproducibility_gap` for
     not-reproducible claims. A semantically equivalent relation is accepted
     when the signal makes the relationship explicit (for example, a source
     that proves a required artifact is absent may use `refutes`).
   - Source paths may be workspace-relative paths or unambiguous basenames.
     Evidence grounding may be distributed across `location`, `signal`, and
     `reproducibility_note`; do not repeat the same phrase merely to satisfy
     multiple fields.

Rules:
- Do not run internet search.
- Do not fabricate rerun logs or claim a reproduction succeeded unless the shipped package supports it.
- Distinguish unsupported, contradicted, overstated, and not reproducible.
