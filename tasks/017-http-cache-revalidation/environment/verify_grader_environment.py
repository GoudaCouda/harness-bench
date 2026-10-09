#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue: object) -> None:
    source = (
        "from datetime import datetime\n"
        "def parsed(value):\n"
        "    return datetime.strptime(value, '%a, %d %b %Y %H:%M:%S GMT').year\n"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.parse(source), "cache_probe.py", "exec"), namespace)
    queue.put(namespace["parsed"]("Wed, 21 Oct 2015 07:28:00 GMT"))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader HTTP-date worker timed out")
observed = queue.get(timeout=1) if process.exitcode == 0 else None
if observed != 2015:
    raise SystemExit(f"grader AST/HTTP-date worker probe failed: {observed}")
print(json.dumps({
    "ast": "passed",
    "http_date_year": observed,
    "multiprocessing_start_method": context.get_start_method(),
}, sort_keys=True))
