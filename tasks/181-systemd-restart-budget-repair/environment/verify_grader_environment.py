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
def plan_systemd_restart_budget(events, policy):
    return {'decisions': [{'unit': row['unit']} for row in events], 'suppressed': 0}
"""
cases=[{"events":[{"unit":"api"}],"policy":{"burst":2}}]
safe,detail=audit_pure_function(source,"plan_systemd_restart_budget")
if not safe:
    raise SystemExit(detail)
actual,detail=run_pure_function(source,"plan_systemd_restart_budget",cases,("events","policy"))
if not actual or actual[0].get("value")!={"decisions":[{"unit":"api"}],"suppressed":0}:
    raise SystemExit(detail)
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"]!=0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    observation,sources_unchanged,workspace_redline_violations
)):
    raise SystemExit("grader systemd-plan API import probe failed")
print(json.dumps({"python3":"3.10","pure_worker":"passed","yaml":"passed"},sort_keys=True))
