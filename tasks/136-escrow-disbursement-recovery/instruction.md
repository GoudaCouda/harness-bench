# Recover an interrupted escrow-disbursement closeout

You are the settlement operations analyst recovering an offline real-estate
escrow batch after the prior local apply crashed. The SQLite ledger contains
several synthetic closings, payee instructions, protected recorded/disbursed
boundaries, an interrupted before-image journal, and a partially written row.
The evidence delivery stream contains out-of-order and duplicate wire,
authorization, recording, and holdback events.

Everything is synthetic and local. Begin with:

```bash
python3 escrowctl.py inspect
```

Then inspect every table in `state/escrow.db`, `policy/escrow_policy.json`,
`evidence/settlement_events.jsonl`, all evidence documents, and their hashes.
Do not trust delivery order: keep the first delivery of each `event_id`, report
later deliveries as duplicates, and apply accepted events per closing in
`source_sequence` order. Unknown closings and ordinary events delivered after
an irreversible disbursement boundary are not applied; a later holdback-release
authorization is evaluated only against the retained holdback.

For each closing, reconcile the received wire, signed closing authorization,
recording status, payee verification, account suffix, instruction amount, and
allocation conservation. A recording timestamp and any completed disbursement
are irreversible. A retained holdback is part of conservation; its later local
release packet requires a matching signed release authorization. A discrepancy
must produce the most specific policy hold, never an inferred correction.

Create `recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "EDR-20260819-01",
  "source_checkpoint": "derived protected-source checkpoint",
  "closing_decisions": [],
  "event_dispositions": [],
  "totals": {},
  "external_actions_executed": false
}
```

Each closing decision has exactly:

```text
closing_id, property_id, disposition, final_state, wire_amount_cents,
authorized_allocations_cents, holdback_cents, next_local_action,
instruction_ids, evidence_refs
```

Each event disposition has exactly:

```text
delivery_id, event_id, closing_id, source_sequence, disposition
```

`instruction_ids` and `evidence_refs` are sets for comparison. Evidence
locators are stable local `file#record` references. `totals` has exactly
`received_wire_cents`, `locally_stageable_cents`,
`preserved_disbursed_cents`, and `retained_holdback_cents`. Use policy
vocabulary verbatim.

Use only the guarded workflow; do not hand-edit the database or generated
staging artifacts:

```bash
python3 escrowctl.py preview recovery_plan.json
python3 escrowctl.py apply recovery_plan.json
python3 escrowctl.py verify recovery_plan.json
python3 escrowctl.py stage recovery_plan.json
python3 escrowctl.py replay recovery_plan.json
```

`preview` reports discrepancies by closing and delivery without mutation.
`apply` restores the interrupted before-image and commits one atomic local
projection. `stage` creates an offline review packet, hash manifest, and local
receipt only. The recovery ID, protected checkpoint, and normalized semantic
plan define replay identity: reordering decisions, event rows, set-valued
fields, or JSON formatting is an equivalent byte-stable no-op; conflicting
content under the same identity and stale checkpoints are rejected before
mutation.

Finally create `escrow_handoff.md`. Explain each hold or stage decision, event
ordering and duplicate handling, wire and allocation conservation, evidence
authority, journal restoration, recorded/disbursed boundaries, holdback release,
packet hashes, and replay. State explicitly that no wire, disbursement,
holdback release, recording, filing, or notification was executed.

Keep policy, evidence, controller, and protected identity/boundary fields
unchanged. Do not use the network or claim any external action.
