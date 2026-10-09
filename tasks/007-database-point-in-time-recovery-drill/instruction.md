# Recover an isolated PostgreSQL incident copy

You are the database reliability engineer for a synthetic PostgreSQL service. An accidental batch transaction damaged production history, and a previous recovery drill created a newer divergent timeline. Build and verify an isolated point-in-time recovery candidate; do not touch, promote, or claim to change production.

Work only in `$WORKSPACE`, with no network. Treat `evidence/`, `policy/`, `pitr_lib.py`, and `pitrctl.py` as immutable. The only existing file you may modify is `state/recovery_state.json`, and only through `pitrctl.py`.

Begin with `python3 pitrctl.py --help`, then inspect `status`, `backups`, `timelines`, and `incident`. Use targeted `backup --id ...` and `wal --timeline ...` queries. A valid checksum is necessary but not sufficient: the backup must match the production system and correct incident timeline, and the required WAL must be continuous through an unambiguous recovery target. Do not use a timestamp target when distinct commits share that timestamp.

Create `work/recovery_plan.json` with:

- `incident_id`, `system_identifier`, `backup_id`, `target_timeline`
- `target_type`, `target_name`, `target_lsn`, `recovery_target_action`; use the
  PostgreSQL recovery-setting spelling `"name"` for `target_type` when the
  evidence calls for `recovery_target_name`
- `required_wal_segments`, `restore_command_template`
- `rationale`, `rejected_alternatives`, and `expected_invariants`;
  `rejected_alternatives` is an array of objects with string fields
  `candidate` and `reason`, and `expected_invariants` is an array of the
  evidence-provided check objects. Use each rejected backup's exact backup ID
  as its `candidate`; identify a rejected time target as
  `timestamp:<ISO-8601 value>`. Reasons must cite the observed defect (for
  example, manifest/checksum evidence, timeline divergence, or a shared
  timestamp), not merely label the candidate "bad" or "ambiguous".

Use the protected workflow:

```text
python3 pitrctl.py verify-backup --id <backup-id>
python3 pitrctl.py validate-plan --plan work/recovery_plan.json
python3 pitrctl.py restore --plan work/recovery_plan.json
python3 pitrctl.py probe
python3 pitrctl.py probe
python3 pitrctl.py close-gate --plan work/recovery_plan.json
python3 pitrctl.py replay --plan work/recovery_plan.json
```

The two probes must be complete and identical. The controller writes `work/probe_report.json` and `work/recovery_receipt.json`. Finish with `work/recovery_handoff.md` explaining backup and timeline selection, rejected alternatives, WAL continuity, named-target reasoning, restored invariants, two-probe/replay evidence, rollback/monitoring steps, and the exact manual-promotion boundary. State that this is an offline synthetic recovery, the candidate is ready only for manual promotion review, production was not changed, no promotion occurred, and no external communication occurred.
