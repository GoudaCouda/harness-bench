# CI recovery policy

The current head SHA is `91ac2e`.

- Preserve current-head passing jobs; do not rerun them.
- Deterministic test, assertion, lint, or documentation failures require a
  matching patch record before a later run. Without one, leave the job blocked.
- A runner-loss job may be retried once. If attempt 2 also loses the runner,
  mark the retry exhausted and escalate rather than scheduling attempt 3.
- Fail-fast cancellation caused by another blocker does not consume retry
  budget; leave it waiting until blockers are resolved.
- Artifacts must come from the final passing current-head attempt. An old-SHA
  success cannot satisfy the run.
- The run is blocked while any required job is unresolved.
