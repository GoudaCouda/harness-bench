#!/usr/bin/env python3
from __future__ import annotations

import ast
import itertools
import json
import multiprocessing

def child(queue) -> None:
    source = "import itertools\ndef choose(values):\n    return list(itertools.combinations(values, 2))\n"
    tree = ast.parse(source)
    namespace = {}
    exec(compile(tree, "resolver_probe.py", "exec"), namespace)
    versions = namespace["choose"](["1.1.0", "1.2.0", "2.0.0"])
    queue.put(versions == list(itertools.combinations(["1.1.0", "1.2.0", "2.0.0"], 2)))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader resolver worker timed out")
if process.exitcode != 0 or queue.get(timeout=1) is not True:
    raise SystemExit("grader AST/itertools worker probe failed")

print(json.dumps({"ast": "passed", "itertools": "passed", "multiprocessing_start_method": context.get_start_method()}, sort_keys=True))
