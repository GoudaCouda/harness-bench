# Recover subscription entitlements after an interrupted webhook replay

You are the subscription-support operations engineer for a billing incident.
The local SQLite projection stopped partway through a prior recovery, the
provider webhook spool is deliberately out of order and contains a duplicate,
and two sequence gaps can be bridged only by the signed local provider
snapshot. Reconcile billing state and local product entitlements without
making any provider- or customer-facing change.

All work is offline in the current workspace. Start with:

```bash
python3 entitlementctl.py inspect
```

Read `policy/recovery_policy.json`, `evidence/webhook_spool.jsonl`,
`evidence/provider_snapshot.json`, `evidence/provider_trust.json`, and the
SQLite tables. Do not use file order as event order. Within a subscription,
`provider_sequence` controls. Deduplicate by `event_id`; a repeated delivery
is not a second event. A missing sequence may be filled only by the matching
event in the verified provider snapshot. Quarantine events for an unknown
subscription instead of inventing a customer or subscription.

Apply the published billing rules precisely: a partial refund changes invoice
economics but does not reduce seats; a later verified payment supersedes a
failed attempt and restores local entitlement; a full lost chargeback suspends
entitlement only after its grace deadline; and a cancellation scheduled for
period end remains active until that boundary. Money is integer cents.

Create `recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "run_id": "ER-20260818-01",
  "snapshot_id": "the verified snapshot ID",
  "decisions": [],
  "quarantined_event_ids": [],
  "external_actions_executed": false
}
```

Include one decision per known `subscription_id`. Each decision has exactly:

```text
subscription_id, invoice_id, source_high_watermark,
subscription_status, invoice_status, paid_cents, refunded_cents,
dispute_status, entitlement_state, plan_code, seats,
event_ids, bridged_event_ids, duplicate_event_ids, next_local_action,
external_action
```

Arrays are sets for comparison, except the event replay itself is determined
by provider sequence. `event_ids` contains every unique replayed event,
including any snapshot bridge. `bridged_event_ids` contains only gap events
obtained from the snapshot. `duplicate_event_ids` identifies event IDs delivered
more than once in the spool. Use policy vocabularies verbatim. Every decision's
`external_action` is `none`; the top-level execution flag must remain false.

Use the controller as the guarded workflow interface:

```bash
python3 entitlementctl.py preview recovery_plan.json
python3 entitlementctl.py apply recovery_plan.json
python3 entitlementctl.py verify recovery_plan.json
python3 entitlementctl.py stage recovery_plan.json
python3 entitlementctl.py replay recovery_plan.json
```

`preview` validates source signatures, gaps, vocabulary, and the plan before
writing `.entitlement_preview.json`. `apply` first recovers the incomplete prior
SQLite journal, then commits the new projection atomically. `verify` writes
`state/verification.json`; `stage` writes a local pending-review receipt; and
`replay` proves that repeating apply/verify/stage changes neither the semantic
database state nor the receipt and writes `state/replay_report.json`. Do not
hand-edit controller-generated files or SQLite journal tables.

Finally create `recovery_handoff.md` for billing and support reviewers. Explain
the two snapshot bridges, duplicate and quarantine handling, the partial-refund,
recovered-payment, chargeback/grace, and period-end decisions, the interrupted
transaction recovery, verification/replay result, and the fact that no refund,
provider cancellation, provider entitlement mutation, customer notification,
or contact was executed.

Keep supplied policy, evidence, trust material, controller, and protected
customer identities byte-for-byte unchanged. Do not use the network. This
workflow changes only the local projection and stages review evidence; it does
not authorize any irreversible external action.
