#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing

def child(queue: object) -> None:
    source = (
        "import re\n"
        "def valid(value):\n"
        "    return bool(re.match(r'^sha256=[0-9a-f]{64}$', value))\n"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.parse(source), "record_probe.py", "exec"), namespace)
    queue.put(namespace["valid"]("sha256=" + "b" * 64))

context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.is_alive():
    process.terminate()
    process.join(1)
    raise SystemExit("grader RECORD worker timed out")
observed = queue.get(timeout=1) if process.exitcode == 0 else None
if observed is not True:
    raise SystemExit(f"grader AST/regex worker probe failed: {observed}")
print(json.dumps({
    "ast": "passed",
    "record_digest_regex": "passed",
    "multiprocessing_start_method": context.get_start_method(),
}, sort_keys=True))
