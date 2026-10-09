# Repair the bounded asynchronous worker pool

You maintain a Python ingestion service. Its worker-pool helper launches every
job at once, returns completion order, lets one exception abort siblings, and
leaks tasks when shutdown times out.

Work only in `$WORKSPACE/repo`. Read `docs/pool_contract.md`, inspect
`src/pool.py`, the protected runner, fixture, and public tests, then repair
`run_batch` as a general asyncio implementation. Do not hard-code visible job
IDs, delays, or values.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python bin/run_batch.py
```

The final runner invocation must generate `out/results.json` and
`out/audit.json`. Re-parse both. Create `POOL_NOTES.md` explaining bounded
queue backpressure, concurrency limits, result ordering, worker-failure
isolation, `get()`/`task_done()` pairing, timeout cancellation, caller
cancellation propagation, cleanup, input validation, exact verification
commands, and their result.

Do not edit the contract, jobs, runner, or tests. Do not use threads, processes,
networking, or files from `src/pool.py`, and do not claim a production run.
