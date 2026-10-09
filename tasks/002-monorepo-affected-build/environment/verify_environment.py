#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import resource
import subprocess
import sys


def child(queue: object) -> None:
    queue.put(sum([1, 2, 3]))


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
alias = subprocess.run(
    ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")
ast.parse("def plan_affected(changed_paths, graph):\n    return sorted(set(changed_paths))\n")
context = multiprocessing.get_context("fork")
queue = context.Queue()
process = context.Process(target=child, args=(queue,))
process.start()
process.join(5)
if process.exitcode != 0 or queue.get(timeout=1) != 6:
    raise SystemExit("multiprocessing fork execution failed")
soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
print(json.dumps({"python": "3.12", "python_alias": alias.stdout.strip(), "fork": "passed", "rlimit_cpu": [soft, hard]}, sort_keys=True))
