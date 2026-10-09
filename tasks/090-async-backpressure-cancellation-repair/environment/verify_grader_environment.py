#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys

import yaml

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")


async def probe() -> bool:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    await queue.put("ready")
    if await queue.get() != "ready":
        return False
    queue.task_done()
    await queue.join()
    task = asyncio.create_task(asyncio.sleep(30))
    task.cancel()
    result = await asyncio.gather(task, return_exceptions=True)
    return task.done() and isinstance(result[0], asyncio.CancelledError)


if not asyncio.run(probe()):
    raise SystemExit("grader asyncio queue/cancellation probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(
    callable(value)
    for value in (
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "asyncio": "queue_cancellation_passed",
            "yaml": "passed",
            "grader_api": "passed",
        },
        sort_keys=True,
    )
)
