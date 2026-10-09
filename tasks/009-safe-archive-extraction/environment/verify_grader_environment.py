#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing


def child(queue: object) -> None:
    source = "def plan(entries, policy):\n    return [row['path'] for row in entries]\n"
    namespace: dict[str, object] = {"__builtins__": {}}
    exec(compile(ast.parse(source), "archive_probe.py", "exec"), namespace)
    queue.put(namespace["plan"]([{"path": "release/app.txt"}], {}))


context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.exitcode != 0 or queue.get(timeout=1) != ["release/app.txt"]:
    raise SystemExit("grader archive preflight worker probe failed")
print(json.dumps({"multiprocessing_start_method": context.get_start_method(), "restricted_ast_worker": "passed"}, sort_keys=True))
