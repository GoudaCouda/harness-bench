#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
import yaml
from harnessbench.grading.pure_function import audit_pure_function, run_pure_function
from harnessbench.grading.task_checks import observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
source = """
def plan_git_worktree_prune(records, policy):
    return {'decisions': [{'id': row['id']} for row in records], 'prune_paths': [], 'repair_paths': []}
"""
cases = [{"records":[{"id":"wt"}],"policy":{"main_path":"/repo"}}]
safe, detail = audit_pure_function(source, "plan_git_worktree_prune")
if not safe:
    raise SystemExit(detail)
actual, detail = run_pure_function(source, "plan_git_worktree_prune", cases, ("records","policy"))
if not actual or actual[0].get("value") != {
    "decisions":[{"id":"wt"}],"prune_paths":[],"repair_paths":[]
}:
    raise SystemExit(detail)
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    observation, sources_unchanged, workspace_redline_violations
)):
    raise SystemExit("grader Git-plan API import probe failed")
print(json.dumps({"python3":"3.10","pure_worker":"passed","yaml":"passed"},sort_keys=True))
