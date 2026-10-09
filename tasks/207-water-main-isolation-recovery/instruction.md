# Recover an interrupted water-main isolation projection

You are the distribution-control planner recovering an **offline synthetic
digital twin** after an isolation-planning worker stopped between changing one
valve projection and closing its SQLite before-image journal. No command in
this exercise can operate a physical valve or contact a utility system.

Begin with `python3 waterctl.py inspect`. Inspect the policy and source
manifest, every row of `evidence/telemetry_events.jsonl`, and the relevant
SQLite tables with `python3 waterctl.py query TABLE`. The controller help lists
the allowed tables.

Reconcile the telemetry as an at-least-once delivery stream. An exact
redelivery is ignored. Every delivery sharing an event identity with a
different body is quarantined. Different event identities occupying the same
valve/source sequence are quarantined. Ignore an unknown valve, a sequence not
newer than that valve's protected high-water mark, and telemetry aimed at a
maintenance-locked valve. Accepted telemetry updates the planning observation,
not the protected source row.

Select one isolation boundary for work order `WO-4471`. A boundary is
admissible only when all of its required valves can close, it crosses no
maintenance lock, and its critical-service outage count is zero. From the
admissible boundaries choose the lowest affected connection count, breaking a
tie by boundary ID. The policy's reason precedence is authoritative. Preserve
every valve that is unavailable, locked, a critical feed, or outside the
selected boundary. This is a local planning projection, not approval to close
anything.

Create `isolation_recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "WIR-20260819-01",
  "source_checkpoint": "derived protected-source checkpoint",
  "work_order_id": "WO-4471",
  "selected_boundary_id": "derived boundary",
  "valve_decisions": [],
  "delivery_dispositions": [],
  "impact_summary": {},
  "external_actions_executed": false
}
```

Include exactly one valve decision for every registered valve, with exactly:

```text
valve_id, observed_operability, desired_position, disposition, reason_codes,
impacted_zone_ids, local_mutations, next_local_action, evidence_refs
```

Include exactly one delivery disposition for every delivered row, with exactly:

```text
delivery_id, event_id, valve_id, source_sequence, disposition
```

`reason_codes`, `impacted_zone_ids`, `local_mutations`, and `evidence_refs` are
sets for semantic comparison. `impact_summary` has exactly
`selected_boundary_id`, `affected_connections`, `critical_service_outages`,
`valves_to_close`, `unavailable_valves`, `protected_valves`, and
`quarantined_deliveries`. Use the published vocabulary and stable local
`file#table:id` or `file#record` evidence locators.

Use the guarded workflow; do not hand-edit SQLite or generated closure files:

```bash
python3 waterctl.py preview isolation_recovery_plan.json
python3 waterctl.py apply isolation_recovery_plan.json
python3 waterctl.py verify isolation_recovery_plan.json
# write isolation_handoff.md before staging
python3 waterctl.py stage isolation_recovery_plan.json
python3 waterctl.py replay isolation_recovery_plan.json
```

`preview` is read-only and reports field mismatches by valve and delivery.
`apply` first restores the open before-image journal and then commits one atomic
local projection. Stable `recovery_id + source_checkpoint` and the normalized
semantic plan define replay identity: JSON formatting, row order, and order in
set-valued fields do not. A stale checkpoint or conflicting plan under the
same recovery identity must fail before writing.

Write `isolation_handoff.md` for distribution control, field operations, and
critical-service reviewers. Explain telemetry authority, every boundary's
admissibility, the selected boundary and impact, each exceptional valve, the
interrupted-journal recovery, packet hashes, verification, and semantic replay.
State explicitly that no physical valve was operated, no water service was
interrupted, and no crew, customer, hospital, regulator, or external system was
contacted or changed.

Keep the policy, evidence, controller, and protected SQLite source fields
byte-for-byte unchanged. Do not use the network or claim a physical operation,
dispatch, outage, notification, approval, or regulatory submission.
