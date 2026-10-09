# Interrupted install recovery

The planner first validates every journal path and digest against the wheel
RECORD evidence. For an interrupted journal it walks applied writes in reverse
order: newly created files are removed, changed files are restored to their
before digest and owners, and identical shared content only detaches the
interrupted package owner. A path already equal to its before snapshot is an
idempotent completed recovery step.

Any post-write drift or unexpected state for an unapplied entry suppresses the
whole rollback action list for manual review. This prevents one apparently safe
restore from overwriting a concurrent edit elsewhere in the same transaction.
Committed journals are left alone.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`; both public tests passed successfully.

Remaining risk: the real executor must atomically recheck current digest and
owner metadata immediately before each reviewed action, because this offline
plan cannot close a time-of-check/time-of-use race. No package operation,
site-packages edit, or deployment was performed.
