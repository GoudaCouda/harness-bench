#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import resource


def child(queue: object) -> None:
    namespace = {"__builtins__": {"sorted": sorted, "set": set}}
    exec(compile(ast.parse("value = sorted(set([3, 1, 3]))"), "probe.py", "exec"), namespace)
    queue.put(namespace["value"])


context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.exitcode != 0 or queue.get(timeout=1) != [1, 3]:
    raise SystemExit("grader restricted-execution fork probe failed")
soft, hard = resource.getrlimit(resource.RLIMIT_AS)
print(json.dumps({"fork": "passed", "restricted_ast": "passed", "rlimit_as": [soft, hard]}, sort_keys=True))
