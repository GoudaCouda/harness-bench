#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue: object) -> None:
    source = "def choose(rows):\n    return sorted(rows, key=lambda row: row['sequence'])[0]\n"
    namespace: dict[str, object] = {"__builtins__": {"sorted": sorted}}
    exec(compile(ast.parse(source), "refresh_probe.py", "exec"), namespace)
    queue.put(namespace["choose"]([{"sequence": 2}, {"sequence": 1}]))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader refresh worker timed out")
observed = queue.get(timeout=1) if process.exitcode == 0 else None
if observed != {"sequence": 1}:
    raise SystemExit(f"grader AST/ordering worker probe failed: {observed}")
print(json.dumps({
    "ast": "passed",
    "ordered_worker": observed,
    "multiprocessing_start_method": context.get_start_method(),
}, sort_keys=True))
