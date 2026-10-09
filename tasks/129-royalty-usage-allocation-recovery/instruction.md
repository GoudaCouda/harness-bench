# Recover an interrupted royalty usage allocation

You are the rights-accounting operations analyst for an offline quarterly music
royalty close. A DDEX-like usage feed arrived out of order with a repeated
event and a later event version. Recording-to-work mappings and ownership
splits are effective-dated. A previous local allocation attempt stopped after
writing one allocation row.

Reconcile the feed and recover the local SQLite ledger without paying anyone,
sending a statement, or contacting a rightsholder. Start with:

```bash
python3 royaltyctl.py inspect
```

Use `royaltyctl.py query events`, `query mappings`, `query rights`, and
`query ledger` to inspect the supplied state. Read `policy/royalty_policy.json`.
The files are synthetic but model a real rights-accounting workflow.

For each logical event, retain the highest event version; identical deliveries
of the same version are one event. Resolve the ISRC recording-to-work mapping
that was uniquely effective on the usage date, then the territory, usage-type,
and date rights window and the uniquely effective ownership split. A negative
adjustment can be allocated only when its target event belongs to this
statement. It inherits the target event's mapping, rights window, and split;
it must not silently use the adjustment date's newer split. Unknown or
ambiguous recordings, events outside a rights window, and cross-statement
adjustments must be quarantined locally. Allocated plus quarantined units and
royalty cents must conserve the canonical source totals, including signs.

Create `royalty_allocation_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "statement_id": "RST-2026Q2-NORTH-01",
  "recovery_id": "ROYREC-20260819-01",
  "source_checkpoint": "derived protected-source checkpoint",
  "actions": [],
  "external_actions_executed": false
}
```

Include exactly one action for each canonical event. Each action has exactly:

```text
event_id, event_version, disposition, recording_id, iswc, mapping_version,
split_version, units, royalty_cents, allocations, evidence_refs
```

`allocations` is empty for quarantine actions. Otherwise it contains objects
with exactly `rightsholder_id`, `units`, and `royalty_cents`. Use the published
disposition vocabulary. `evidence_refs` are stable local `file#record`
locators and are a set for semantic comparison. Action, evidence, and
allocation ordering is not meaningful.

Use the guarded workflow instead of editing the database or receipts:

```bash
python3 royaltyctl.py preview royalty_allocation_plan.json
python3 royaltyctl.py apply royalty_allocation_plan.json
python3 royaltyctl.py verify royalty_allocation_plan.json
python3 royaltyctl.py stage royalty_allocation_plan.json
python3 royaltyctl.py replay royalty_allocation_plan.json
```

`apply` must recover the interrupted row and atomically commit the statement
once. `stage` creates only an internal receipt in
`pending_rights_accounting_review`; it is not a payment or delivered royalty
statement. The stable statement/recovery identity and protected source
checkpoint bind the operation. An equivalent plan with reordered actions,
evidence, allocations, or JSON formatting must replay as a no-op. A conflict
under the same identity must be rejected without mutation.

Finally write `royalty_handoff.md` for rights and royalty reviewers. Explain
event de-duplication/version selection, mapping and split effective dates,
each quarantine reason, the same-statement negative adjustment rule, signed
money and unit conservation, interrupted-journal recovery, verification,
staging, and replay. State explicitly that no payment was executed, no
statement was sent, and no rightsholder was contacted.

Keep policy, source feeds, controller, and protected ledger metadata unchanged.
Do not use the network or claim any irreversible external action.
