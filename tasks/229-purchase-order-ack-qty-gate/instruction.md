# Admit purchase-order acknowledgments only at or below ordered quantity

You are the buyer at Harborwatch Procurement. A batch is parked for handoff.
A vendor note says over-ack is a courtesy ship and should be accepted. Policy disagrees.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/incident_brief.md`
- `staging/ack_batch.json`
- `poctl.py`

## Deliverables

- `state/ack_log.json`: One decision per item, the decision counts, and the id lists.
- `state/ack_receipt.json`: The same counts and id lists.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `po_ack_handoff.md`: Explain the look-alike conflict, why envelope failures
  are malformed, the verification you performed, and the authorization
  boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before recording decisions; it is authoritative over
   `evidence/incident_brief.md` where they disagree.
2. Equal ack quantity is admitted. Partial ack is held as backorder. Over-ack is malformed, not a raise of the ordered quantity.
3. Use `python3 poctl.py validate` for feedback, and run it more than once so
   your verification record reflects repeat behavior rather than a single pass.
4. Do not contact an external system, release funds, notify a partner, file a
   report, or delete evidence. This is an offline local decision.
