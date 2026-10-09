# Recover an interrupted multi-carrier shipment-claim batch

You are the claims operations analyst recovering a local shipment-claim batch.
The SQLite portfolio contains prior cases, claim lines, evidence-blob metadata,
an interrupted journal, and immutable submitted/closed boundaries. Carrier event
deliveries include out-of-order sequences, a replayed event, a denial deadline,
a supplement for a duplicate case, an unknown case, and a supplement delivered
after a case was already closed and paid.

Everything is synthetic and offline. Start by running:

```bash
python3 claimsctl.py inspect
python3 claimsctl.py contract --json
```

`contract --json` is the authoritative public syntax contract. It reports the
current protected-source checkpoint, exact plan/row field sets, controlled
vocabulary, nullable/set-valued fields, and locator grammar. These are interface
facts, not a completed claims plan: you must still derive every claim and event
outcome from the evidence, policy, and restored SQLite baseline. Copy the
reported 64-hex `source_checkpoint` into the candidate plan; do not substitute a
recovery ID, source revision, manifest hash, or interrupted-run ID.

Then inspect `policy/claims_policy.json`, `evidence/carrier_events.jsonl`, the
evidence files, their recorded hashes, and every relevant SQLite table in
`state/claims.db`. Do not trust delivery order: de-duplicate by `event_id`, then
apply accepted events by carrier sequence. Same-tracking cases resolve to the
oldest opened case (case ID breaks a tie), and a supplement for a merged case is
routed to that survivor.

Apply the published evidence and settlement rules per claim line. Damage with
intact shipment identity but missing packaging may be locally staged only at the
policy's partial percentage; shortage requires a signed BOL; and an invoice
whose shipment identity does not match the claim is a hold, not settlement
evidence. Acknowledging an already-submitted case must not create a new
submission. Closed/paid and submitted timestamps, paid amounts, tracking
identity, and carrier identity are irreversible or protected.

Create `recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "CRR-20260819-01",
  "source_checkpoint": "derived protected-source checkpoint",
  "decisions": [],
  "event_dispositions": [],
  "totals": {},
  "external_actions_executed": false
}
```

Each decision has exactly:

```text
case_id, tracking_number, carrier, survivor_case_id, disposition,
final_state, requested_amount_cents, locally_allowed_amount_cents,
response_deadline, next_local_action, claim_line_ids, evidence_refs
```

Each event disposition has exactly:

```text
delivery_id, event_id, source_case_id, effective_case_id,
carrier_sequence, disposition
```

`claim_line_ids` and `evidence_refs` are sets for comparison. Use only the
controlled values reported by `contract --json`; similar labels such as
`settled`, `preserved`, `accepted`, `rejected`, `hold`, `stage_packet`, or
`send_denial_response` are not contract values. Evidence locators must follow
the reported grammar exactly. In particular, SQLite locators identify a table
and key, blob locators end in their blob ID (not a JSON array index), and carrier
event locators end in the event ID. `totals` has exactly `active_requested_amount_cents`,
`ready_packet_amount_cents`, `preserved_submitted_amount_cents`, and
`preserved_paid_amount_cents`.

Use the guarded workflow; do not hand-edit the database or generated staging
artifacts:

```bash
python3 claimsctl.py preview recovery_plan.json
python3 claimsctl.py apply recovery_plan.json
python3 claimsctl.py verify recovery_plan.json
python3 claimsctl.py stage recovery_plan.json
python3 claimsctl.py replay recovery_plan.json
```

`apply` first restores the interrupted journal and then commits one atomic local
projection. `stage` creates only a local packet bundle, its hash manifest, and a
receipt. Denial responses are ordered by their response deadline before ordinary
ready packets. The stable recovery ID, protected source checkpoint, and
normalized semantic plan define replay identity: reordering decisions, event
dispositions, set-valued fields, or JSON formatting is an equivalent no-op;
conflicting content under the same identity must be rejected without mutation.
`preview` validates your candidate first and reports differing fields separately
for each claim, delivery, and total; it does not reveal expected claim outcomes.
Use that feedback to repair the candidate before `apply`.

Finally create `claims_handoff.md`. Explain the duplicate survivor, event
ordering/replay decisions, evidence authority for each settlement/hold, denial
deadline priority, interrupted-journal recovery, immutable submitted and closed
cases, packet hash closure, and replay result. State that the packet remains
local and no claim or response was submitted, no carrier was contacted, and no
payment or refund was executed.

Keep policy, evidence, controller, and protected claim identity/boundary fields
unchanged. Do not use the network or claim an external action.
