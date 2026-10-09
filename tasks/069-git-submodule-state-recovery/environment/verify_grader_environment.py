#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import sys

from harnessbench.grading.pure_function import audit_pure_function, run_pure_function

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """def plan_submodule_recovery(submodules, recursive):
    rows = [row for row in submodules if recursive or row.get("depth") == 0]
    return sorted(rows, key=lambda row: row["path"])
"""
tree = ast.parse(source)
if [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)] != ["plan_submodule_recovery"]:
    raise SystemExit("AST function discovery probe failed")
safe, detail = audit_pure_function(
    source,
    "plan_submodule_recovery",
    allowed_methods=("get",),
    max_nodes=7000,
)
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
result, detail = run_pure_function(
    source,
    "plan_submodule_recovery",
    [{"submodules": [{"path": "b", "depth": 1}, {"path": "a", "depth": 0}], "recursive": False}],
    ("submodules", "recursive"),
)
if not result or result[0].get("value") != [{"path": "a", "depth": 0}]:
    raise SystemExit(f"isolated planner replay probe failed: {detail}")
if multiprocessing.get_context("spawn").get_start_method() != "spawn":
    raise SystemExit("spawn worker probe failed")

print(json.dumps({"python3": "3.10", "ast": "passed", "pure_function": "passed", "isolated_replay": "passed"}, sort_keys=True))
