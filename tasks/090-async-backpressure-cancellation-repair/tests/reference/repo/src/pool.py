import asyncio


async def run_batch(items, worker, *, concurrency, queue_size, shutdown_after=None):
    if not isinstance(items, list) or not callable(worker):
        raise ValueError("invalid batch")
    if type(concurrency) is not int or not 1 <= concurrency <= 16:
        raise ValueError("invalid concurrency")
    if type(queue_size) is not int or not 1 <= queue_size <= 1024:
        raise ValueError("invalid queue size")
    if shutdown_after is not None:
        if type(shutdown_after) not in (int, float) or shutdown_after <= 0 or shutdown_after != shutdown_after or shutdown_after in (float("inf"), float("-inf")):
            raise ValueError("invalid shutdown deadline")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "payload"} or not isinstance(item["id"], str) or not item["id"] or item["id"] in seen:
            raise ValueError("invalid item")
        seen.add(item["id"])
    if not items:
        return []

    queue = asyncio.Queue(maxsize=queue_size)
    stop = object()
    results = [None] * len(items)

    async def produce():
        for index, item in enumerate(items):
            await queue.put((index, item))
        for _ in range(concurrency):
            await queue.put(stop)

    async def consume():
        while True:
            entry = await queue.get()
            try:
                if entry is stop:
                    return
                index, item = entry
                try:
                    value = await worker(item)
                except Exception:
                    results[index] = {"id": item["id"], "status": "error", "error": "worker_failed"}
                else:
                    results[index] = {"id": item["id"], "status": "ok", "value": value}
            finally:
                queue.task_done()

    producer = asyncio.create_task(produce())
    consumers = [asyncio.create_task(consume()) for _ in range(concurrency)]
    tasks = [producer] + consumers

    async def finish():
        await producer
        await queue.join()
        await asyncio.gather(*consumers)

    async def cleanup():
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                queue.task_done()

    timed_out = False
    try:
        if shutdown_after is None:
            await finish()
        else:
            try:
                await asyncio.wait_for(finish(), shutdown_after)
            except TimeoutError:
                timed_out = True
                await cleanup()
    except asyncio.CancelledError:
        await cleanup()
        raise
    if timed_out:
        for index, item in enumerate(items):
            if results[index] is None:
                results[index] = {"id": item["id"], "status": "cancelled", "reason": "shutdown"}
    return results
