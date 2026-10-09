# Repair a paginated research evidence graph without inferring missing entities

You are a research intelligence analyst repairing an offline OpenAlex-style evidence graph export. The export has DOI aliases, missing pages, expected-row mismatches, duplicate works, same-name authors, stale affiliation notes, missing DOI records, dangling references, one unresolved relation conflict, one correction event that resolves a different same-DOI disagreement, and downstream works that must inherit review-required state through graph references.

Work only in `$WORKSPACE`. Useful inputs include:
- `pages_index.json`
- `works_page1.json`
- `works_page2.json`
- `works_page4.json`
- `authors.json`
- `concepts.json`
- `correction_events.json`
- `prior_graph_state.json`
- `policy.md`

The export stopped after the page-2 checkpoint. Use `graphctl.py` as the local
resume interface: run `python3 graphctl.py --help` and `status`, then use
`inspect-page` before `consume-page` for each still-unrecorded declared page.
The controller must record both an available page and a declared-but-missing
page; it does not decide DOI identity, graph status, or business correctness.
Do not hand-edit `.graph_repair_state.json`.

## Deliverables

- `evidence_graph.csv`
- `coverage.json`
- `graph_audit.md`

The graph is a handoff to another analyst. Use stable local IDs, preserve unresolved cases explicitly, and do not infer missing pages, identities, affiliations, or DOI facts.

## Working rules

1. Read `pages_index.json` first. Consume every available declared page, report declared pages whose files are absent, and compare declared `expected_rows` with observed rows for available pages.
2. Normalize DOI URL, `doi:` prefix, case, and whitespace. Apply the version-alias rule in `policy.md` for duplicate works; do not treat every `-v2` suffix as a duplicate.
3. Keep authors separate by `author_id`; display names are never identity keys. Orphan authors in `authors.json` must be reported. Missing current affiliation remains `unknown` even if a stale note mentions an older affiliation.
4. Preserve missing DOI evidence. If a local note suggests a possible DOI but the work has no DOI, mark it as `quarantined_suspected_match`; do not fill `canonical_key` from the note.
5. Apply `correction_events.json` before the generic conflict rule. A named correction event resolves only the work ids it names; unresolved conflicts still require quarantine.
6. If the same canonical work appears with conflicting `claim_relation` values and no correction event resolves it, mark every row for that canonical work `quarantined_conflict`.
7. After resolving corrections and quarantines, apply the contagion rule in `policy.md`: works that depend on quarantined or review-required works become `review_required`, and this propagation is transitive.
8. Preserve dangling references to absent works in the graph row and report them as `source_work_id->missing_work_id`.
9. Reconcile `prior_graph_state.json` with the current export. Keep still-valid prior states, release prior review holds only when current evidence resolves them, and record every status transition in `coverage.json`.
10. Derive `coverage.json` from the final graph ledger and the prior checkpoint. Do not hand-edit totals independently.
11. In `graph_audit.md`, explain pagination coverage, row-count mismatches, duplicate and non-duplicate version alias decisions, same-name author separation, suspected DOI quarantine, correction handling, unresolved conflict quarantine, review-required propagation, checkpoint reconciliation, dangling references, orphan authors, verification, and the offline safety boundary.
12. Keep every source file byte-for-byte unchanged. Do not use the network or claim an external API/production action was executed.
13. After creating all three deliverables, run `python3 graphctl.py validate`
    and fix every reported interface or reconciliation error. Then run
    `python3 graphctl.py stage` followed by `python3 graphctl.py replay` twice.
    Both replays must pass while `.graph_repair_state.json` and
    `graph_stage_receipt.json` remain byte-for-byte stable. Staging is a local
    handoff checkpoint, not an external OpenAlex update.

## Output format

Create the deliverables named below. Use the listed file names exactly and keep all evidence references local to the visible workspace inputs. Do not cite hidden files, generated outputs, URLs, absolute paths, or parent-directory paths as evidence.

- `evidence_graph.csv`: `csv` artifact.
  Use these columns in order: `work_id`, `canonical_work_id`, `canonical_key`, `author_ids`, `institution_ids`, `referenced_work_ids`, `concept_ids`, `claim_relation`, `status`, `issue`, `evidence_refs`.
- `coverage.json`: `json` artifact.
  Include these top-level fields: `pages_consumed`, `pages_declared_not_found`, `page_row_count_mismatches`, `prior_checkpoint_id`, `prior_processed_pages`, `new_pages_consumed`, `observed_work_rows`, `canonical_works`, `duplicate_works`, `non_duplicate_version_aliases`, `authors`, `authors_named_alex_kim`, `unknown_affiliations`, `orphan_authors`, `quarantined_works`, `conflicting_canonical_works`, `resolved_correction_works`, `review_required_works`, `review_required_edges`, `dangling_references`, `state_changes`, `supporting_works`, `contradicting_works`.
- `graph_audit.md`: `markdown` artifact.

For structured files, derive row sets, object keys, counts, totals, and status values from the visible evidence and the workflow rules rather than from a separate answer contract.
