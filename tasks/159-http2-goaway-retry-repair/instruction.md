# Repair an HTTP/2 GOAWAY retry planner

An API client retries every unfinished HTTP/2 stream after GOAWAY. That can
duplicate non-idempotent side effects, while refusing all retries loses the
protocol's `last-stream-id` safety signal. Work only in `/workspace/repo`.

Read `docs/goaway_contract.md`, inspect the connection observation, request
ledger, policy, runner, and public tests, then repair
`src/goaway_recovery.py` as a general pure implementation. Run public tests and
`python bin/plan_retries.py`; re-parse `out/decisions.json` and
`out/summary.json`. Write `RETRY_NOTES.md` covering GOAWAY last-stream
semantics, completed and unprocessed streams, `REFUSED_STREAM`, ambiguous
processed requests, method idempotency, idempotency keys, replayable bodies,
retry/error budgets, fresh connections, validation, commands/results, and the
offline/no-network boundary.

Do not send HTTP requests, reconnect to a service, replay a production body,
or claim that any live request was retried.
