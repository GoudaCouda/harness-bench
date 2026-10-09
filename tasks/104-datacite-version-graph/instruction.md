# Repair and stage a DataCite dataset-version repository migration

You are the metadata curator for an offline research repository. A provider
attempted to publish a major 2026 cohort by reusing the findable `v3` DOI. The
staging database also contains a wrong-direction version relation, duplicate
edges, a self-edge, a draft public edge, duplicate citations, and a prior
checkpoint that must remain auditable.

Work only in `$WORKSPACE`. Read `policy.md` first. DataCite's versioning pattern
has been adapted into a synthetic offline repository: a major update receives a
new DOI, the canonical concept and version DOIs use `HasVersion` / `IsVersionOf`,
and adjacent versions use `IsNewVersionOf` / `IsPreviousVersionOf`.

The protected `repository_seed.db` is the dirty reset point. `repository.db` is
the writable staging database. Use the local interface rather than editing the
seed:

1. Run `python3 repoctl.py --help` and `python3 repoctl.py status`.
2. Inspect all three tables with `repoctl.py inspect --table records`, `edges`,
   and `change_log`. Inspect their column contracts with `repoctl.py schema
   --table NAME`, especially the initially empty `change_log`, then inspect the
   JSON evidence and prior checkpoint.
3. Create `migration.sql` at the workspace root. It must transactionally repair
   `repository.db` when run from the protected seed. Use only `INSERT`,
   `UPDATE`, and scoped `DELETE` statements against the existing `records`,
   `edges`, and `change_log` tables. Write DML only: do not include `BEGIN`,
   `COMMIT`, or `ROLLBACK`, because the controller supplies the transaction.
   Do not create or drop schema objects, use filesystem paths, attach a
   database, or bulk-delete a table.
4. Run `python3 repoctl.py apply --file migration.sql`. The controller always
   applies the migration to a temporary copy of the protected seed, runs graph
   lint, and replaces `repository.db` only on success. Revise the SQL from its
   feedback. `repoctl.py reset` is available if you need to restore the dirty
   database explicitly.

## Required repository result

- Add the findable public version `10.data/cohort.v4` for change
  `CH-2026-04`; preserve findable v1, v2, and v3 and preserve the draft record
  as a draft record.
- The public edge graph must exclude the draft DOI, duplicates, self-edges, and
  cycles. It must contain both concept/version directions for every public
  version and both adjacent-version directions for v1→v2→v3→v4.
- Repair R3's direction. Collapse R4/R5 to one canonical edge. Remove R9 and
  R10 from the public graph without deleting their source evidence.
- Collapse C1/C1-DUP. Keep the pre-update C1 citation on v2. Retarget C2 to v4
  because it is post-update and explicitly describes the new cohort. Keep C3
  on the concept DOI.
- Every final edge needs a nonempty unique `edge_id` and one of these statuses: `retained`, `added`,
  `corrected_direction`, `deduplicated`, `retargeted`, or
  `preserved_concept_citation`, plus decisive local `evidence_refs` separated
  by semicolons.
- Append one stable, unique `change_log` row, with a nonempty unique
  `change_id`, for each exact action value:
  `add_version`, `correct_direction`, `remove_duplicate`, `remove_self_edge`,
  `remove_draft_edge`, `remove_duplicate_citation`, and `retarget_citation`.
  Self-edge and draft-edge removals are separate rows. `source_ref` must be one
  visible `basename#record_id`; use `before_value` and `after_value` to state
  the old/new identifier, relation, disposition, or an explicit empty/none
  boundary. Do not record an external submission or DOI registration.

## Handoff artifacts

Create `graph_validation.json` with exactly these top-level fields:
`new_version`, `concept`, `versions`, `excluded_records`,
`removed_invalid_edges`, `corrected_direction_edges`,
`duplicate_relation_edges_removed`, `duplicate_citations_removed`,
`citation_retargets`, `citation_preserved`, `old_versions_retained`, `cycles`,
`self_edges`, `prior_checkpoint_id`, and `state_changes`.

`state_changes` contains `added_edges`, `corrected_edges`, `removed_edges`,
`retained_edges`, `retargeted_citations`, and `unchanged_citations`. Use
`from_doi|relation|to_doi` for edge identities. Counts must be JSON integers;
closed ID/edge collections must be JSON arrays. Derive the validation from the
actual final database and `prior_graph_state.json`.

Create `version_decision.md` explaining the major-version decision, old-version
retention, topology and invalid-edge repairs, each citation decision, checkpoint
reconciliation, database verification, and the offline/no-external-action
boundary. Equivalent professional wording is allowed.

Keep `change.json`, `citations.json`, `policy.md`, `prior_graph_state.json`,
`records.json`, `relations.json`, `repository_seed.db`, and `repoctl.py`
unchanged. Do not use the network, register or update a real DOI, or claim an
external repository action.

After the database and both handoff artifacts are complete, run
`python3 repoctl.py validate`, fix every error, and then run
`python3 repoctl.py stage`. Staging is local only and creates a hash-bound
`.repository_stage_state.json` plus `repository_stage_receipt.json`. Finally
run `python3 repoctl.py replay` twice; both runs must pass and leave state and
receipt byte-for-byte stable.
