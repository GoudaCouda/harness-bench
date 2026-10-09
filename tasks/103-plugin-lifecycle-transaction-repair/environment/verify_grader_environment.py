#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml

from harnessbench.grading.pure_function import audit_pure_function, expected_results, run_pure_function
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
from collections import defaultdict
from copy import deepcopy

def reconcile_plugins(state, catalog, request, faults):
    graph = defaultdict(set)
    for plugin in catalog:
        graph[plugin["name"]].update(plugin["depends"])
    return {"state": deepcopy(state), "nodes": sorted(graph)}
"""
safe, detail = audit_pure_function(
    source,
    "reconcile_plugins",
    allowed_imports=("collections", "copy"),
    allowed_methods=("deepcopy", "update"),
)
if not safe:
    raise SystemExit(f"pure-function lifecycle audit probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (
    expected_results,
    run_pure_function,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "pure_function_graph": "passed"}, sort_keys=True))
