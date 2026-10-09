# Recover an interrupted wheel install

A local package installer crashed while applying a wheel. Its current recovery
planner can delete shared files and can overwrite edits made after the crash.
Repair the offline planner; do not change the environment it describes.

Work only inside `repo/`. Read `repo/docs/recovery_contract.md`, the visible
case batch, implementation, and public tests before editing.

Deliver:

1. Repair `repo/src/install_recovery.py`, preserving the public function
   `plan_recovery(site_state, journal, wheel_record)`. Validate the transaction,
   plan rollback in reverse write order, preserve shared ownership, fail closed
   on post-crash drift, support an idempotent retry, and leave inputs unchanged.
2. Create `repo/recovery_report.json`: an array in visible-case order containing
   each `case_id` and the exact plan returned by the repaired function.
3. Create `repo/RECOVERY_NOTES.md` explaining the rollback, ownership, drift,
   and retry decisions; include the exact verification command and observed
   result, plus one remaining integration risk.

Run from `repo/`:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not edit the contract, journal fixtures, wheel records, or public tests. Do
not install/uninstall a package, modify site-packages, or claim a deployment.
