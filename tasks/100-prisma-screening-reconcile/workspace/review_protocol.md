# Registered screening protocol v2.1

## Scope and eligibility

Include reports of controlled or randomized workplace interventions that
report measured outcomes. Exclude editorials, protocols without results,
non-workplace populations, non-controlled designs, and reports without measured
outcomes. When more than one exclusion applies, use this registered precedence:

1. `editorial`
2. `wrong_publication_type`
3. `wrong_population`
4. `wrong_design`
5. `no_measured_outcomes`

Use `full_text_unavailable` only when the export explicitly says that the full
text could not be retrieved; do not infer an eligibility decision for that
report.

## Report deduplication and study linkage

- Normalize DOI values by removing a leading `https://doi.org/` or `doi:`,
  trimming whitespace and terminal punctuation, and lowercasing the remainder.
- Equal normalized DOI values identify the same report.
- If one occurrence lacks a DOI, an exact PMID match establishes the same
  report. Otherwise require agreement on normalized title, first author, year,
  and the same trial identity from `registry_crosswalk.csv`.
- A shared trial identity establishes the same study, not necessarily the same
  report. A conference abstract and full article, or a protocol and results
  article, remain distinct report entities even when linked to one study.
- A similar title alone is insufficient to merge reports or studies. Preserve
  distinct trial IDs and populations.
- Choose any stable internal report and study IDs. Exactly one database row in
  each report entity is `canonical`; its other occurrences are `duplicate`.

## Flow accounting

Let one source row be one identified record and one report entity be one report
sought for retrieval.

- `records_identified` = all source rows.
- `duplicate_records_removed` = source rows marked `duplicate`.
- `reports_sought_for_retrieval` = report entities after source deduplication.
- `reports_not_retrieved` = canonical reports decided `not_retrieved`.
- `reports_assessed_for_eligibility` = reports sought minus reports not retrieved.
- `reports_excluded` = assessed reports decided `exclude`.
- `included_reports` = assessed reports decided `include`.
- `included_studies` = distinct study entities represented by included reports.
- `flow_closes` is true only when identified minus duplicates equals sought;
  sought minus not retrieved equals assessed; and assessed minus excluded equals
  included reports.
