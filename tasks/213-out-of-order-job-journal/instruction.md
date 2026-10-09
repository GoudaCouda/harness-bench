# Reconcile an out-of-order CI job journal without promoting failed attempts

You are the build-systems engineer at Ridgeway. A completion stream arrived
out of order after the dispatcher stalled. `job-b` completed before `job-a`,
and a later event tries to mark a failed attempt succeeded without incrementing
the attempt number.

Work only in `$WORKSPACE`. Useful inputs:
- `policy.md`
- `evidence/incident_brief.md`
- `state/jobs.json`
- `staging/completions.json`
- `journalctl.py`

## Deliverables

- `state/jobs.json`: Update jobs in place to the statuses this stream actually
  applied, including any jobs still held or failed.
- `state/journal_receipt.json`: Every apply/hold/block/replay/stale/reject
  decision in stream order plus drained holds, with counts.
- `state/verification.json`: Controller command, each attempt, and whether
  re-running it left the state unchanged.
- `job_journal_handoff.md`: Explain hold-and-drain, the failed dependency,
  the stale succeed, verification, and the boundary.

## Working rules

1. Read `policy.md` first. Walk the completion stream in listed order.
2. Hold completions whose dependencies have not succeeded; drain holds after
   each successful apply. Do not treat a same-attempt succeed after fail as
   a retry.
3. Use `python3 journalctl.py validate` more than once.
4. Modify only `state/jobs.json` and create only the three declared handoff
   artifacts.

Work offline. Do not execute or claim an external, production, payment,
filing, deletion, message-send, booking, or account action.
