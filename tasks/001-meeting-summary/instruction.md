# Recover a crashed DNSSEC rollover staging run

You are the DNS operations engineer recovering synthetic offline run
`ROL-2026-08-A` after its local staging worker crashed between durable SQLite
writes and checkpoint persistence. The checkpoint is stale in both directions,
and an interrupted write changed one zone row and inserted one queue row without
closing its before-image journal.

Everything is local and uses reserved example zones and synthetic public keys.
Nothing reaches authoritative DNS or a registrar. Begin by inspecting the
environment:

```bash
python3 dnssecctl.py inspect
python3 dnssecctl.py query "SELECT * FROM zones ORDER BY zone_name"
python3 dnssecctl.py query "SELECT * FROM rollover_journal ORDER BY journal_id"
python3 dnssecctl.py query "SELECT * FROM staging_queue ORDER BY queue_id"
```

Read every policy and evidence file, the stale checkpoint, the zone snapshots,
the public key files, and every SQLite table. The policy publishes the timing,
authority, vocabulary, and locator rules. In particular:

- A KSK decision is controlled by parent-DS observations from the required
  probes and their dwell time. A DNSKEY observation or desired checkpoint phase
  does not prove parent publication.
- A ZSK decision is controlled by DNSKEY prepublication dwell and observed RRSIG
  coverage/validity; parent DS is not part of the ZSK path.
- Restore interrupted before-images in your reasoning before classifying any
  zone. Preserve serials and key facts: this recovery only rebuilds an
  **unexecuted local queue**.

Create `rollover_recovery.json` with exactly these top-level fields:

```text
schema_version, recovery_id, source_checkpoint, rollover_id,
zone_decisions, journal_actions, external_actions_executed
```

Each zone decision has exactly `zone_name`, `key_role`, `rollover_phase`,
`current_serial`, `ttl_dwell_state`, `signature_state`, `parent_ds_state`,
`action`, and `evidence_refs`. Each journal action has exactly `journal_id`,
`table_name`, `record_id`, and `action`. Use the field vocabulary and stable
locator grammar in `policy/rollover_policy.json`. Evidence references compare
as sets.

Use the guarded local workflow; do not hand-edit SQLite or generated staging
artifacts:

```bash
python3 dnssecctl.py preview rollover_recovery.json
python3 dnssecctl.py apply rollover_recovery.json
python3 dnssecctl.py stage rollover_recovery.json
python3 dnssecctl.py verify rollover_recovery.json
python3 dnssecctl.py replay rollover_recovery.json
```

`preview` reports failed fields per zone and journal without changing SQLite.
`apply` first restores interrupted before-images, then atomically records the
decisions and an offline queue; it never edits a zone file, signs a zone, or
contacts a parent. `stage` writes a local bundle, manifest, and receipt. Stable
recovery ID, source checkpoint, and normalized business plan define replay
identity: reordered zone decisions, journal actions, evidence references, or
JSON formatting are equivalent no-ops. Conflicting content under that identity
and stale source revisions must reject without mutation.

Write `dnssec_recovery_handoff.md`. Explain the checkpoint disagreements, the
restored partial write, KSK parent-DS versus ZSK prepublication reasoning,
serial/signature safeguards, every zone disposition, local queue scope, hash
closure, independent verification, and idempotent replay. State explicitly
that no zone was signed or published, no DNS/registrar/parent change occurred,
and all queued actions remain unexecuted.

Do not modify policy, evidence, checkpoint, public keys, zone snapshots,
controller, protected durable state, or completed run history. Do not use the
network or claim an external DNS action was completed.
