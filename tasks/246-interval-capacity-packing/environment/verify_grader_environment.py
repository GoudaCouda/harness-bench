#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing


def child(queue: object) -> None:
    source = "def resolve(defaults, override):\n    return override if override is not None else defaults\n"
    namespace: dict[str, object] = {"__builtins__": {}}
    exec(compile(ast.parse(source), "config_probe.py", "exec"), namespace)
    queue.put([namespace["resolve"](True, False), namespace["resolve"](8080, None)])


context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.exitcode != 0 or queue.get(timeout=1) != [False, 8080]:
    raise SystemExit("grader typed-config worker probe failed")
print(json.dumps({"multiprocessing_start_method": context.get_start_method(), "typed_false_and_null": "passed"}, sort_keys=True))
