# Recover an Interrupted CDC/SCD2 Materialization

You are recovering the local customer-dimension materialization for batch `CDC-2026-08-19-42`. The worker stopped after durably preparing one event. The redelivery also contains an exact duplicate, an out-of-order but complete version chain, a stale update, a signed historical correction, and records that cross published safety boundaries.

Work only inside `$WORKSPACE`; all external systems are offline. Read every declared source before deciding dispositions:

- `warehouse.db`
- `initial_warehouse.json`
- `cdc_batch.jsonl`
- `recovery_policy.md`
- `schema_registry.json`
- `retention_holds.csv`
- `signed_corrections.json`

`cdcctl.py` is the local controller. Start with `python3 cdcctl.py --help`, then use its inspection/query commands. Do not edit the controller or evidence files.

Create `recovery_plan.json` with these top-level fields:

- `schema_version`: `1`
- `batch_id`
- `source_sha256`: SHA-256 of the unmodified `cdc_batch.jsonl`
- `actions`: one object per **unique** `event_id`, containing `event_id`, `disposition`, and a non-empty `evidence_refs` list
- `external_publish_executed`: `false`

Use only the dispositions published by `recovery_policy.md`. Evidence references must be local locators such as `cdc_batch.jsonl#EV-401`; do not cite generated outputs, hidden files, URLs, absolute paths, or parent paths.

Then complete the executable workflow:

1. `python3 cdcctl.py preview recovery_plan.json`
2. `python3 cdcctl.py apply recovery_plan.json`
3. run the same `apply` again and confirm it reports an idempotent replay
4. `python3 cdcctl.py verify`
5. write `recovery_handoff.md`
6. `python3 cdcctl.py stage recovery_plan.json`
7. run `stage` again and confirm the staged receipt is unchanged

Required final artifacts:

- modified `warehouse.db`
- `recovery_plan.json`
- `cdc_verification.json`
- `cdc_stage_receipt.json`
- `recovery_handoff.md`

The handoff must explain the complete version chain, duplicate/stale handling, signed correction and inheritance, every quarantine boundary, the interrupted-prepare recovery, verification, replay result, and that no publish, notification, or external warehouse action occurred.

Do not create substitute databases or manually forge controller receipts. Keep `initial_warehouse.json`, `cdc_batch.jsonl`, policy, registry, holds, signed corrections, and `cdcctl.py` byte-for-byte unchanged.
