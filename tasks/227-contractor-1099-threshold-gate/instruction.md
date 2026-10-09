# Admit 1099 rows only for contractors at or above the reporting threshold

You are the tax-operations analyst at Harborwatch Payables. A batch is parked for handoff.
AP labeled an employee invoice as contractor so it would hit 1099. Policy disagrees.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/incident_brief.md`
- `staging/payee_batch.json`
- `taxctl.py`

## Deliverables

- `state/payee_log.json`: One decision per item, the decision counts, and the id lists.
- `state/payee_receipt.json`: The same counts and id lists.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `ten99_threshold_handoff.md`: Explain the look-alike conflict, why envelope failures
  are malformed, the verification you performed, and the authorization
  boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before recording decisions; it is authoritative over
   `evidence/incident_brief.md` where they disagree.
2. Classification in the HR record wins over the invoice label. Employees are held. Contractors admit at or above 60000 cents.
3. Use `python3 taxctl.py validate` for feedback, and run it more than once so
   your verification record reflects repeat behavior rather than a single pass.
4. Do not contact an external system, release funds, notify a partner, file a
   report, or delete evidence. This is an offline local decision.
