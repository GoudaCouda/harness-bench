# Repair HTTP request retry safety

An API client retries every timeout and 5xx response. A lost response after a
POST can therefore create duplicate jobs or charges. Repair the offline retry
planner before any request is replayed.

Work only in `repo/`. Preserve
`plan_http_retry(request, attempt_number, observation)`. Read the retry
contract, broken implementation, visible incidents, and public tests.

Deliver repaired `repo/src/retry_planner.py`, ordered `repo/retry_report.json`
with every visible `case_id` and exact result, and `repo/RETRY_NOTES.md`.
Explain send-phase evidence, idempotent methods, enforced idempotency keys,
unknown outcomes, status/application state, exponential delay,
`Retry-After`, exhaustion, verification, and residual live-client risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not make an HTTP request, replay an operation, create or charge
anything, mutate a service, or claim an external action.
