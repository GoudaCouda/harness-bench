# Recover a concurrent OAuth refresh race

Two workers refreshed the same expiring OAuth session. The current reconciler
can overwrite a rotated token with a stale response or retry a replay signal.
Repair the offline state reconciler; do not call either OAuth endpoint.

Work only inside `repo/`. Read `repo/docs/refresh_contract.md`, the visible case
batch, implementation, and public tests before editing.

Deliver:

1. Repair `repo/src/refresh_recovery.py`, preserving
   `reconcile_refresh(session, attempts)`. It must validate state, ignore stale
   generations, choose safe single-flight outcomes in completion order, honor
   rotation, fail closed on replay/drift signals, and leave inputs unchanged.
2. Create `repo/reconciliation_report.json`, an array in visible-case order with
   each `case_id` and the exact reconciliation returned by the repaired function.
3. Create `repo/RECOVERY_NOTES.md` explaining winner selection, rotation,
   `invalid_grant`, stale attempts, and retry behavior; include the exact test
   command/result and one remaining integration risk.

Run from `repo/`:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not edit fixtures, the contract, or public tests. Do not expose real secrets,
refresh a token, revoke a grant, or claim production state changed.
