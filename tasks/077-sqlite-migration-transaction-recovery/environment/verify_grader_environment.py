#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys

import yaml

from harnessbench.grading.pure_function import audit_pure_function, run_pure_function
from harnessbench.grading.task_checks import sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
import re
def plan_migration_recovery(migration, db_state, observation):
    return {"decision": observation.get("phase"), "actions": list(migration.get("statements", []))}
"""
safe, detail = audit_pure_function(source, "plan_migration_recovery", allowed_imports=("re",))
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
manifest = yaml.safe_load("schema_version: 2\npass_threshold: 0.8\n")
if manifest["pass_threshold"] != 0.8 or re.fullmatch(r"[0-9a-f]{64}", "a" * 64) is None:
    raise SystemExit("YAML/regex probe failed")
if not all(callable(value) for value in (run_pure_function, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "pure_function": "passed"}, sort_keys=True))
