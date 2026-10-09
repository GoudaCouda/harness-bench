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
def plan_version_sync(release_tag, previous_tag, manifests):
    return {"release": release_tag.lstrip("v"), "changes": sorted(manifests, key=lambda row: row["path"])}
"""
safe, detail = audit_pure_function(source, "plan_version_sync", allowed_imports=("re",))
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
manifest = yaml.safe_load("schema_version: 2\ncases: []\n")
if manifest != {"schema_version": 2, "cases": []}:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (run_pure_function, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader API import probe failed")
if re.fullmatch(r"v?\d+\.\d+\.\d+", "v1.2.3") is None:
    raise SystemExit("regex probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "pure_function": "passed"}, sort_keys=True))
