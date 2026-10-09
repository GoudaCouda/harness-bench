# CI recovery diagnosis

The current-head unit and lint successes are preserved. Windows consumed its
one runner retry and passed on attempt 2. macOS also consumed one retry, but the
second runner was lost, so its budget is exhausted and operator escalation is
required rather than an unsupported third attempt.

Integration was a deterministic assertion failure and has matching patch
evidence before its passing attempt 2. Docs still has a broken-link code
failure with no patch evidence, so it remains blocked at attempt 1. E2E was
cancelled by fail-fast and waits for the unresolved blockers without consuming
runner retry budget.

The old-SHA package artifact was replaced by the current-head passing artifact
with digest `sha256:new91`. Verification reconciled eight unique jobs at head
`91ac2e`: macOS, docs, and E2E remain pending, so the run is blocked. This is an
offline evidence handoff; no patch, rerun, upload, or external action was
executed here.
