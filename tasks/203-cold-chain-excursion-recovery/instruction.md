# Recover cold-chain holds after a logger gap

You are the cold-chain quality coordinator for an immunization depot. During the
fall daylight-saving transition, the primary logger for one container stopped
reporting and another container has an apparently similar gap. A previous local
hold transaction stopped after changing one lot. Reconcile the logger evidence,
recover the SQLite inventory, and stage a QA review packet.

Everything is offline in the current workspace. Start with:

```bash
python3 coldchainctl.py inspect
```

Read `policy/cold_chain_policy.json`, the evidence bundle, and relevant SQLite
tables. Timestamps in logger records are local wall time plus an explicit UTC
offset; the repeated 01:00 hour is intentional. Duplicate readings must be
deduplicated by device and sequence. A primary gap may be filled only by a
secondary device assigned to the same container for the whole gap, with an
in-force calibration and a signed range manifest whose checksum covers the
selected readings. Apply the calibration offset before threshold evaluation.

Temperature outside the inclusive policy band is an excursion only when the
duration from the first through last consecutive out-of-band reading meets the
policy duration. Transport and door-open events can explain a pattern but cannot
waive a hold or quarantine. If authoritative evidence cannot close a gap, hold
the lot for QA rather than guessing.

Create `excursion_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "CCR-20261101-01",
  "source_checkpoint": "derived protected-source checkpoint",
  "decisions": [],
  "external_actions_executed": false
}
```

Include exactly one decision for every in-scope lot. Each has exactly:

```text
lot_id, container_id, primary_device_id, gap_intervals_utc,
fallback_device_id, fallback_calibration_id, observed_min_c, observed_max_c,
out_of_range_minutes, disposition, local_mutations, evidence_refs,
next_local_action
```

`gap_intervals_utc`, `local_mutations`, and `evidence_refs` are sets for
comparison. Use policy vocabularies verbatim. Use `null` for unavailable
fallback or temperature fields. Evidence references are stable local
`file#record` locators.

Use the guarded workflow; do not hand-edit the database or generated receipts:

```bash
python3 coldchainctl.py preview excursion_plan.json
python3 coldchainctl.py apply excursion_plan.json
python3 coldchainctl.py verify excursion_plan.json
python3 coldchainctl.py stage excursion_plan.json
python3 coldchainctl.py replay excursion_plan.json
```

`apply` first restores the interrupted before-image, then commits the exact local
hold/quarantine projection atomically. Stable `recovery_id + source_checkpoint`
identifies the recovery. Reordering decisions or set-valued fields and changing
JSON formatting is the same semantic plan and must replay without mutation. A
conflicting plan for the same identity, or a stale checkpoint, must be rejected
before writing.

Finally write `cold_chain_handoff.md` for QA and inventory reviewers. Explain
logger authority, DST normalization, duplicate handling, calibration and signed
range validation, each lot disposition, the partial-journal recovery, and
verification/replay. State clearly that you did not destroy or release stock,
administer vaccine, notify recipients/regulators, or perform any external action.

Preserve supplied policy, evidence, controller, and protected inventory/device
identity fields byte-for-byte. Do not use the network or claim an irreversible
action.
