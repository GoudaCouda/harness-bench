# Reconcile the review search and close the PRISMA flow

You are the screening coordinator for a systematic review of controlled
workplace interventions. A PubMed CSV and a Scopus RIS export overlap, but
identifiers are inconsistently formatted and some studies have more than one
report. The review lead needs a defensible deduplication ledger and a PRISMA
flow that can be regenerated from that ledger.

Work only in `$WORKSPACE`. Read all of these local sources:

- `review_protocol.md`
- `pubmed_export.csv`
- `scopus_export.ris`
- `registry_crosswalk.csv`
- `screening_ledger_template.csv`

Do not use the network or modify the sources. Create exactly these two files at
the workspace root; do not add notes, reports, or other deliverables:

## 1. `screening_ledger.csv`

Use the template columns, in its existing order, and write exactly one row for
every source record in the two exports:

```text
source_record_id,canonical_report_id,study_id,normalized_doi,record_status,eligibility_decision,exclusion_reason,evidence
```

- `canonical_report_id` and `study_id` are stable IDs you assign. Their spelling
  is not prescribed. Use 1–64 ASCII characters, begin with a letter or digit,
  and use only letters, digits, `.`, `_`, `:`, or `-` thereafter. Their grouping
  must be correct and internally consistent.
- `normalized_doi` is the report DOI after applying the protocol's
  normalization, or an empty cell when no linked source establishes a DOI.
- `record_status` is `canonical` for exactly one source row in each report
  entity and `duplicate` for its other database occurrences.
- On a canonical row, `eligibility_decision` is `include`, `exclude`, or
  `not_retrieved`. On a duplicate source row it is `duplicate_record`.
- `exclusion_reason` is empty for an included report; otherwise use the reason
  code defined by the protocol. A duplicate row uses `duplicate_source_record`.
- `evidence` contains the visible locators that support the row. Use
  `pubmed_export.csv#<source_record_id>` or
  `scopus_export.ris#<source_record_id>` for export records, and
  `registry_crosswalk.csv#<canonical_trial_id-or-alias>` when the crosswalk is
  needed. Separate distinct locators with semicolons. Every row must cite its
  own export record; the canonical row for a duplicated report must cite every
  occurrence of that report. Where linkage depends on a crosswalk row, cite
  either that row's canonical trial ID or its alias. This includes the P02/S02
  missing-DOI reconciliation. Cite only locators that support the row; do not
  add unrelated valid locators.

Do not collapse distinct reports merely because they concern the same study.
Do not invent a merge where the visible evidence is insufficient.

## 2. `prisma_flow.json`

Write a JSON object with exactly these fields and no others:

```text
records_identified
duplicate_records_removed
reports_sought_for_retrieval
reports_not_retrieved
reports_assessed_for_eligibility
reports_excluded
included_reports
included_studies
flow_closes
```

Derive every value from the final ledger using the formulas in
`review_protocol.md`; do not hand-edit totals independently.

Before finishing, reparse the CSV and JSON, confirm that every source ID occurs
once. The ledger itself is the audit trail: report and study grouping,
disposition, registered precedence, retrieval state, and source evidence must
all be recoverable from its structured rows. Keep the CSV at exactly eight
cells per row. Use standards-compliant JSON with unique keys (no `NaN` or
infinity). Output cells and JSON strings must not contain Unicode control or
format characters, including a BOM; CSV cells must not be spreadsheet-formula
text beginning with `=`, `+`, `-`, or `@` after whitespace.
