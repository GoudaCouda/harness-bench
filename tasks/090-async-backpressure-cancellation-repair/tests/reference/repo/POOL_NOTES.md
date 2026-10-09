# Async pool repair handoff

The implementation uses one bounded asyncio Queue with `queue_size` as its
maximum buffer, so producer backpressure prevents one task per input. A fixed
set of consumers enforces the concurrency limit. Results are stored by input
index, preserving input order even though workers finish in a different order.
An ordinary worker failure becomes a `worker_failed` row without cancelling
siblings.

Every successful queue `get()` has `task_done()` in a finally block. On the
internal timeout, producer and consumers are cancelled and awaited, queued
entries are drained with balanced accounting, completed results are retained,
and incomplete rows become shutdown cancellations. Caller cancellation follows
the same cleanup but is re-raised. Input validation, including duplicate IDs,
boolean bounds, malformed rows, and non-finite deadlines, occurs before any
worker call, so invalid inputs fail without side effects.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` and
`PYTHONDONTWRITEBYTECODE=1 python bin/run_batch.py`; both completed
successfully. I parsed the result and audit files, confirmed original ID order,
three successes, one isolated worker failure, and peak concurrency two under a
limit of two. This was a local synthetic run only; no production ingestion,
thread, process, network, or external execution was performed.
