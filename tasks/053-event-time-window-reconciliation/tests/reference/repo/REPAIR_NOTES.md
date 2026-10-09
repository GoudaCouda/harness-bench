# Repair notes

Windows are assigned from event time, never ingestion time. Exact replayed IDs
are idempotent, conflicting reuse fails, and accepted events increment an
existing window revision once per reconciliation. Windows with end after the
watermark remain pending; a window is final exactly when end plus allowed
lateness is less than or equal to the watermark. New events for final windows
are dropped while already-owned replay IDs remain no-ops.

Verification succeeded with
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all public
tests passed. Residual risk: a production checkpoint must atomically persist
event ownership, aggregate, revision, and watermark before acknowledging source
offsets. No stream replay, checkpoint commit, or deployment was performed.
