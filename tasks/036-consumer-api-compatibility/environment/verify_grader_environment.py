#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue) -> None:
    source = "def added_required(before, after):\n    return sorted(set(after) - set(before))\n"
    tree = ast.parse(source)
    namespace = {}
    exec(compile(tree, "compatibility_probe.py", "exec"), namespace)
    queue.put(namespace["added_required"](["id"], ["tenant", "id"]))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader compatibility worker timed out")
if process.exitcode != 0 or queue.get(timeout=1) != ["tenant"]:
    raise SystemExit("grader AST/schema worker probe failed")

print(json.dumps({
    "ast": "passed",
    "schema_sets": "passed",
    "multiprocessing_start_method": context.get_start_method(),
}, sort_keys=True))
