# Recover a crashed credential-rotation projection

Recover synthetic incident `INC-CR-204` after an offline credential-rotation
worker crashed between durable account writes and checkpoint persistence. The
checkpoint is stale in both directions, and one in-progress local write must be
restored from its SQLite before-image before any recovery queue is rebuilt.

Everything is local and synthetic. Begin with:

```bash
python3 credentialctl.py inspect
python3 credentialctl.py query "SELECT * FROM accounts ORDER BY account_id"
python3 credentialctl.py query "SELECT * FROM durable_markers ORDER BY account_id"
python3 credentialctl.py query "SELECT * FROM recovery_journal ORDER BY journal_id"
```

Also inspect `policy/`, `evidence/`, `state/stale_checkpoint.json`, every
SQLite table, and the source manifest. Durable markers scoped to this incident
and the policy target version outrank the stale checkpoint. A compromised
account with no matching durable marker remains pending at its recovered
before-image version. A clean account is preserved even if the checkpoint says
otherwise. An expected target or validation expectation never proves a
rotation occurred.

Create `recovery_plan.json` with exactly these top-level fields:

```text
schema_version, recovery_id, source_checkpoint, incident_id,
account_decisions, journal_actions, external_actions_executed
```

Each account decision has exactly `account_id`, `classification`,
`checkpoint_relation`, `current_version`, `target_version`, `action`,
and `evidence_refs`. Each journal action has exactly `journal_id`,
`table_name`, `record_id`, and `action`. Use the enumerated vocabulary
and locator grammar in `policy/rotation_policy.json`. Evidence references are
sets for comparison.

Run the guarded workflow; do not hand-edit SQLite or generated artifacts:

```bash
python3 credentialctl.py preview recovery_plan.json
python3 credentialctl.py apply recovery_plan.json
python3 credentialctl.py stage recovery_plan.json
python3 credentialctl.py verify recovery_plan.json
python3 credentialctl.py replay recovery_plan.json
```

`preview` gives per-account field and evidence-category pass/fail diagnostics
without modifying the database or disclosing corrected values. `apply`
restores all interrupted before-images and atomically builds
an offline queue; it does not rotate or revoke anything. `stage` creates a
local queue bundle, manifest, and receipt. Stable recovery ID, source
checkpoint, and the normalized semantic plan define replay identity: reordered
decisions, journal actions, evidence references, or JSON formatting are
equivalent no-ops. Conflicting content under that identity and stale source
checkpoints must be rejected without mutation.

Write `credential_recovery_handoff.md` explaining both checkpoint mismatch
directions, durable-marker authority, expected versus observed versions, the
before-image restoration, per-account decisions, local queue scope, hash
closure, verification, and idempotent replay. State that no credential was
rotated or revoked and no external service, account, notification, or incident
state was changed.

Do not modify policy, evidence, the checkpoint, the controller, protected
durable markers, or completed/clean account facts. Do not use the network or
represent an external action as completed.
