# Re-evaluate a protected merge queue after a late commit

You are the protected-branch queue operator. A conflict-resolution commit
changed the queued SHA after the previous checks and reviews completed. The new
snapshot is split between commit metadata, current check runs, and reviews; it
also introduces a license failure that was not present in round one.

Use only these local inputs in `$WORKSPACE`:

- `policy.md`
- `round1.json`
- `round2_update.json`
- `current_checks.json`
- `current_reviews.json`

Create these deliverables in `$WORKSPACE`:

- `queue_gates.csv`, with columns `gate,sha,status,next_action,evidence` in that
  order and one row for every required gate;
- `queue_state.json`, containing `current_sha`, `previous_sha`, `queue_state`,
  `merge_executed`, and the exact `pending_gates` derived from the ledger;
- `transition.md`, an operator handoff explaining invalidated prior evidence,
  current results, exact remediation/revalidation, and the no-merge boundary.

Use round one only as prior history. Every final gate row must target the
current SHA and cite the current file that establishes its status. A passed
current review may be retained; old-SHA approvals and checks may not. Failed,
pending, stale, or missing gates all belong in `pending_gates` because they
prevent merge, but retain their distinct statuses and next actions.

Re-parse the CSV and JSON, reconcile all six gates to aggregate queue state,
and leave the item in queue without merging. Do not modify source evidence,
use the network, trigger checks or review requests, or claim any external/
production action was executed.
