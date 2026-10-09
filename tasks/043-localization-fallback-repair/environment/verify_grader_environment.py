#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue) -> None:
    source = "import re\ndef names(text):\n    return re.findall(r'{([A-Za-z_][A-Za-z0-9_]*)}', text)\n"
    tree = ast.parse(source)
    namespace = {}
    exec(compile(tree, "message_probe.py", "exec"), namespace)
    queue.put(namespace["names"]("Bonjour {name}"))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader localization worker timed out")
if process.exitcode != 0 or queue.get(timeout=1) != ["name"]:
    raise SystemExit("grader AST/regex worker probe failed")

print(json.dumps({"ast": "passed", "re": "passed", "multiprocessing_start_method": context.get_start_method()}, sort_keys=True))
