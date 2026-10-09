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
def plan_multipart_resume(session, local_parts, remote_pages):
    return {"decision": session.get("state"), "pending_parts": sorted(part["part_number"] for part in local_parts)}
"""
safe, detail = audit_pure_function(source, "plan_multipart_resume", allowed_imports=("re",))
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if re.fullmatch(r"[0-9a-f]{64}", "f" * 64) is None:
    raise SystemExit("SHA-256 regex probe failed")
if not all(callable(value) for value in (run_pure_function, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader API import probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "pure_function": "passed"}, sort_keys=True))
