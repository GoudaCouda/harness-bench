#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import sys

from harnessbench.grading.pure_function import audit_pure_function

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """def decide_run(config, stdin_text):
    return {
        'action': 'blocked',
        'exit_code': 2,
        'confirmation': 'invalid_confirmation',
        'stdin_consumed': True,
    }
"""
tree = ast.parse(source)
if [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)] != ["decide_run"]:
    raise SystemExit("AST function discovery probe failed")
safe, detail = audit_pure_function(
    source,
    "decide_run",
    allowed_methods=("get", "strip"),
    max_nodes=6000,
)
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
if multiprocessing.get_context("spawn").get_start_method() != "spawn":
    raise SystemExit("isolated pure-function worker probe failed")

print(json.dumps({"python3": "3.10", "ast": "passed", "pure_function": "passed", "multiprocessing": "passed"}, sort_keys=True))
