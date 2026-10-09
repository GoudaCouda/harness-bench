#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue) -> None:
    source = (
        "def reconcile(state, requests, now_ms):\n"
        "    active = [item for item in state['leases'] if item['expires_ms'] > now_ms]\n"
        "    return sorted(active, key=lambda item: item['fence'])\n"
    )
    tree = ast.parse(source)
    namespace = {}
    exec(compile(tree, "lease_probe.py", "exec"), namespace)
    value = namespace["reconcile"](
        {"leases": [{"expires_ms": 10, "fence": 2}, {"expires_ms": 11, "fence": 1}]},
        [],
        10,
    )
    queue.put(value)

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader lease worker timed out")
if process.exitcode != 0 or queue.get(timeout=1) != [{"expires_ms": 11, "fence": 1}]:
    raise SystemExit("grader AST/lease worker probe failed")

print(json.dumps({"ast": "passed", "multiprocessing_start_method": context.get_start_method()}, sort_keys=True))
