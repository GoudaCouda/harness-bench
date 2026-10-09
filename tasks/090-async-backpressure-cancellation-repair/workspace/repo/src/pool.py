import asyncio


async def run_batch(items, worker, *, concurrency, queue_size, shutdown_after=None):
    """Broken pool: unbounded fan-out, completion order, and sibling failure."""
    tasks = [asyncio.create_task(worker(item)) for item in items]
    results = []
    for task in asyncio.as_completed(tasks):
        value = await task
        results.append({"id": "unknown", "status": "ok", "value": value})
    return results
