#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import sys

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
source = (
    "def reconcile_event_windows(events, prior_windows, watermark_ms, "
    "allowed_lateness_ms, window_ms):\n"
    "    return {'windows': [], 'pending': [], 'dropped_late': []}\n"
)
tree = ast.parse(source)
functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
if functions != ["reconcile_event_windows"]:
    raise SystemExit(f"AST worker probe failed: {functions!r}")
if multiprocessing.get_context("spawn").get_start_method() != "spawn":
    raise SystemExit("isolated pure-function worker probe failed")

print(json.dumps({"python3": "3.10", "ast": "passed", "multiprocessing": "passed"}, sort_keys=True))
