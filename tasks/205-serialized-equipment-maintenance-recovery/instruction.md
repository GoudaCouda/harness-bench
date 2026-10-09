# Recover an interrupted serialized-equipment field-service batch

You are the maintenance planner recovering an offline dispatch batch for
serialized packaging equipment. The local SQLite system contains work orders,
asset identity, effective BOM rows, technician qualifications, calibrated
instruments, service-part lots, an interrupted journal, and an already-completed
repair that must never be reopened. The incoming work-order stream contains
out-of-order observations, a byte-identical duplicate delivery, an event for a
duplicate work order, an unknown order, and a late event for completed work.

Everything is synthetic and offline. Begin with:

```bash
python3 maintenancectl.py inspect
```

Inspect `policy/maintenance_policy.json`, `evidence/work_order_events.jsonl`,
`policy/source_manifest.json`, and every SQLite table in `state/maintenance.db`.
Do not trust delivery order. De-duplicate by `event_id`, then use event sequence.
Orders with the same serialized asset and alarm group resolve to the oldest open
order (work-order ID breaks a tie), and observations for a duplicate route to
the survivor.

For each surviving open order, use its incident time to select the effective BOM
part. A dispatch is locally ready only when a technician holds the required
model/skill qualification at the planning `as_of`, the required instrument is
active and its calibration remains valid, and a released positive-quantity lot
matches the effective part. Quarantined, exhausted, superseded, or wrong-part
lots are not substitutes. Choose the lexicographically first eligible technician,
instrument, and lot when several qualify. Preserve completed execution facts,
commissioning identity, and asset/work-order identity exactly.

Create `maintenance_recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "FSR-20260819-04",
  "source_checkpoint": "derived protected-source checkpoint",
  "assignments": [],
  "event_dispositions": [],
  "totals": {},
  "external_actions_executed": false
}
```

Each assignment has exactly:

```text
work_order_id, asset_serial, survivor_work_order_id, disposition, final_state,
symptom_codes, selected_bom_revision, required_part_number, allocated_part_lot,
technician_id, qualification_code, instrument_id, next_local_action, evidence_refs
```

Each event disposition has exactly:

```text
delivery_id, event_id, source_work_order_id, effective_work_order_id,
sequence, disposition
```

`symptom_codes` and `evidence_refs` are sets for comparison. Use policy
vocabulary verbatim and stable local `file#record` evidence locators. `totals`
has exactly `ready_dispatch_count`, `held_count`, `merged_count`,
`preserved_completed_count`, and `allocated_part_count`.

Use the guarded workflow; do not hand-edit SQLite or generated artifacts:

```bash
python3 maintenancectl.py preview maintenance_recovery_plan.json
python3 maintenancectl.py apply maintenance_recovery_plan.json
python3 maintenancectl.py verify maintenance_recovery_plan.json
python3 maintenancectl.py stage maintenance_recovery_plan.json
python3 maintenancectl.py replay maintenance_recovery_plan.json
```

`apply` first restores the interrupted before-image and then performs one atomic
local projection. `stage` produces a hash-bound offline dispatch bundle; it does
not dispatch technicians, reserve parts externally, issue permits, energize
equipment, or execute maintenance. The stable recovery ID, protected source
checkpoint, and normalized semantic plan define replay identity. Reordering
assignments, event dispositions, set-valued fields, or JSON formatting is an
equivalent no-op. Conflicting content under the same identity must be rejected
without mutation.

Finally create `maintenance_handoff.md`. Explain event ordering and duplicate
routing, BOM effectivity, each qualification/calibration/part-lot decision, the
interrupted-journal restoration, completed-work protection, allocation
conservation, packet hashes, and replay result. State that everything remains
local: no technician was dispatched, no part was externally reserved or
installed, no permit or lockout was executed, and no equipment was energized.

Keep policy, evidence, controller, asset identity, work-order identity, and
already-executed facts unchanged. Do not use the network or claim an external
action.
