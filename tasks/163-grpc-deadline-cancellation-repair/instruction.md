# Repair gRPC deadline and cancellation planning

An RPC gateway retries failures with a fresh full timeout, retries calls after
response headers commit them, and leaves child RPCs running after callers
cancel. Work only in `/workspace/repo`.

Read `docs/rpc_contract.md`, inspect the call ledger, policy, runner, and public
tests, then repair `src/rpc_budget.py` as a general pure implementation. Run
public tests and `python bin/plan_calls.py`; re-parse `out/decisions.json` and
`out/summary.json`. Write `RPC_NOTES.md` covering propagated remaining time,
reserve and exponential backoff, per-try caps, committed response headers,
retryable status, idempotency, attempt exhaustion, parent-operation restart,
caller cancellation and child cleanup, validation, commands/results, and the
offline/no-RPC boundary.

Do not make RPCs, cancel live calls, restart an operation, change a service
config, or claim production retries.
