#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue: object) -> None:
    source = (
        "from datetime import datetime\n"
        "def before(left, right):\n"
        "    fmt = '%Y-%m-%dT%H:%M:%SZ'\n"
        "    return datetime.strptime(left, fmt) < datetime.strptime(right, fmt)\n"
    )
    namespace: dict[str, object] = {}
    tree = ast.parse(source)
    exec(compile(tree, "datetime_probe.py", "exec"), namespace)
    queue.put(namespace["before"]("2026-05-31T23:59:59Z", "2026-06-01T00:00:00Z"))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader datetime worker timed out")
if process.exitcode != 0 or queue.get(timeout=1) is not True:
    raise SystemExit("grader AST/datetime worker probe failed")
print(json.dumps({
    "ast": "passed",
    "datetime": "passed",
    "multiprocessing_start_method": context.get_start_method(),
}, sort_keys=True))
