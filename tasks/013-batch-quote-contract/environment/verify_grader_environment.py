#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue: object) -> None:
    source = (
        "def quote(cents, discount_bps):\n"
        "    discount = cents * discount_bps // 10000\n"
        "    return {'discount': discount, 'total': cents - discount}\n"
    )
    namespace: dict[str, object] = {"__builtins__": {}}
    exec(compile(ast.parse(source), "quote_probe.py", "exec"), namespace)
    queue.put(namespace["quote"](280500, 500))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader pricing worker timed out")
observed = queue.get(timeout=1) if process.exitcode == 0 else None
if observed != {"discount": 14025, "total": 266475}:
    raise SystemExit(f"grader AST/integer-pricing worker probe failed: {observed}")
print(json.dumps({
    "ast": "passed",
    "integer_pricing": observed,
    "multiprocessing_start_method": context.get_start_method(),
}, sort_keys=True))
