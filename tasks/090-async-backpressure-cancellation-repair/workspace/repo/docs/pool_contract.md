# Async worker-pool contract

Implement:

```python
async def run_batch(items, worker, *, concurrency, queue_size, shutdown_after=None)
```

## Validation

Validate everything before invoking `worker`:

- `items` is a list of objects, each with exactly `id` and `payload`;
- every `id` is a non-empty string and unique; payload is opaque;
- `worker` is callable;
- `concurrency` is an integer from 1 through 16 (booleans are invalid);
- `queue_size` is an integer from 1 through 1024 (booleans are invalid);
- `shutdown_after` is null or a positive integer/float (booleans and non-finite
  values are invalid).

Raise `ValueError` before any worker call for invalid input. An empty valid list
returns an empty list.

## Normal completion

Use a bounded `asyncio.Queue(maxsize=queue_size)` producer/consumer design; do
not create one task per item and do not merely wrap unbounded fan-out in a
semaphore. At most `concurrency` worker calls may run simultaneously.

Return one result per item in original input order:

- success: `{"id": ID, "status": "ok", "value": WORKER_RESULT}`;
- ordinary worker exception: `{"id": ID, "status": "error", "error":
  "worker_failed"}`.

An ordinary `Exception` from one worker is isolated and does not cancel other
items. Worker results are opaque JSON-compatible values. Each successful
`queue.get()` must have exactly one `task_done()` in a `finally` path, including
when the worker is cancelled.

## Shutdown and cancellation

If `shutdown_after` elapses before the producer, queue, and workers fully
finish, cancel producer and consumers, await their termination, drain any
queued entries with balanced `task_done()`, and return every already completed
result plus `{"id": ID, "status": "cancelled", "reason": "shutdown"}` for
each incomplete item, still in input order. The function must not leak any task
it created.

If the caller cancels `run_batch`, perform the same complete cleanup and then
re-raise `asyncio.CancelledError`; do not convert caller cancellation into a
result list. Do not catch `BaseException` as an ordinary worker failure.

`src/pool.py` may import only `asyncio`. It must not access files, environment,
network, threads, processes, reflection, private attributes, or dynamic code.
