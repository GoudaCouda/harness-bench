#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import subprocess
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 090 requires CPython 3.12 in the shared agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )


async def queue_and_cancellation_probe() -> dict[str, object]:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    await queue.put(7)
    value = await queue.get()
    queue.task_done()
    await queue.join()

    started = asyncio.Event()

    async def blocked() -> None:
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(blocked(), name="task090-environment-probe")
    await started.wait()
    task.cancel()
    cancelled = False
    try:
        await task
    except asyncio.CancelledError:
        cancelled = True
    return {"queue_value": value, "cancelled": cancelled, "task_done": task.done()}


result = asyncio.run(queue_and_cancellation_probe())
if result != {"queue_value": 7, "cancelled": True, "task_done": True}:
    fail(f"asyncio queue/cancellation probe failed: {result!r}")

probe = subprocess.run(
    [
        "python",
        "-B",
        "-c",
        "import asyncio,json,pathlib,unittest,sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
    ],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0:
    fail(f"python alias/stdlib probe failed: {probe.stderr.strip()}")
if probe.stdout.strip() != "3.12":
    fail(f"python alias is not CPython 3.12: {probe.stdout.strip()!r}")

print(json.dumps({"python": "3.12", "python3": "3.12", "asyncio": result}, sort_keys=True))
