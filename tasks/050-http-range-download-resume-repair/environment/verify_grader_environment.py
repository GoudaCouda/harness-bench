#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import sys

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
tree = ast.parse(
    "def reconcile_resume(manifest, checkpoint, response):\n"
    "    return {'action': 'restart', 'reason': 'probe', 'offset': 0}\n"
)
functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
if functions != ["reconcile_resume"]:
    raise SystemExit(f"AST function audit probe failed: {functions!r}")
if multiprocessing.get_context("spawn").get_start_method() != "spawn":
    raise SystemExit("isolated pure-function worker probe failed")

print(json.dumps({"python3": "3.10", "ast": "passed", "multiprocessing": "passed"}, sort_keys=True))
