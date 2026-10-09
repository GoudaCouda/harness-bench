#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue) -> None:
    source = "import copy\ndef isolate(value):\n    return copy.deepcopy(value)\n"
    tree = ast.parse(source)
    namespace = {}
    exec(compile(tree, "isolation_probe.py", "exec"), namespace)
    original = {"items": []}
    cloned = namespace["isolate"](original)
    cloned["items"].append(1)
    queue.put(original == {"items": []} and cloned == {"items": [1]})

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate(); process.join(1)
    raise SystemExit("grader isolation worker timed out")
if process.exitcode != 0 or queue.get(timeout=1) is not True:
    raise SystemExit("grader AST/deepcopy worker probe failed")

print(json.dumps({"ast": "passed", "copy": "passed", "multiprocessing_start_method": context.get_start_method()}, sort_keys=True))
