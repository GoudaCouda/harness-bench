# Repair notes

The planner treats the superproject gitlink as authoritative and ignores every
remote tip as a recovery target. It distinguishes uninitialized, mismatched,
verified, missing-object, conflicted, dirty, and untracked states; conflict and
local work block before any checkout plan. Recursive records are included only
when requested, and missing commits require an explicit object-acquisition step.

Verification: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
completed successfully with all public tests passing. Residual risk remains in
the executor: it must recheck status immediately before init or checkout and
must never translate a plan into fetch, reset, clean, push, or `--remote`.
