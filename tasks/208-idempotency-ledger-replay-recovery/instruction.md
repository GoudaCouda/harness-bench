# Recover a settlement idempotency ledger after a lost replay worker

You are the settlement platform engineer on call at Northgate Clearing. A
settlement replay worker was fenced mid-batch and left the idempotency ledger
inconsistent: it holds records it finished, a lease it claimed but never
completed, and at least one record that had already left its retention window.
The overnight replay queue was never acknowledged, and a second worker is still
running with a lease of its own.

Finance needs a reconciliation an auditor can read, and no invoice may be
settled twice.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/crash_report.md`
- `state/ledger.json`
- `staging/replay_queue.json`
- `ledgerctl.py`

## Deliverables

- `state/ledger.json`: Recover this existing ledger in place, so that the
  records it keeps are exactly the ones still usable under the policy, plus
  whatever this recovery settles.
- `state/recovery_receipt.json`: Record what the recovery reclaimed, one
  decision per queued request, the decision counts, and the amount this
  recovery actually settled.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `ledger_recovery_handoff.md`: Explain the crash state, why each class of
  request resolved the way it did, why no invoice settled twice, the
  verification you performed, and the authorization boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before changing state; it is authoritative over the ledger
   contents and over `evidence/crash_report.md` where they disagree.
2. Recover the ledger before deciding queued requests, and apply the published
   decision precedence in order.
3. Preserve a record whose lease is still live, and never settle its key here.
4. Use `python3 ledgerctl.py validate` for feedback, and run it more than once so
   your verification record reflects repeat behavior rather than a single pass.
5. Modify only `state/ledger.json` and create only the three declared handoff
   artifacts.

Keep all source evidence byte-for-byte unchanged except for a path explicitly
named as an in-place deliverable. Work offline. Do not execute or claim an
external, production, payment, filing, deletion, message-send, booking, or
account action. Before finishing, re-open the final JSON files and reconcile
their keys and totals across the handoff.
