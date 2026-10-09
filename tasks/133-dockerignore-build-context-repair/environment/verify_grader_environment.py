#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import hashlib
import json
import sys

import yaml
from harnessbench.grading.task_checks import observation, sources_unchanged, substantive_prose, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
paths = ["config/default.json", "config/local.json"]
selected = [name for name in paths if fnmatch.fnmatch(name, "config/*.json") and name.endswith("default.json")]
if selected != ["config/default.json"]:
    raise SystemExit("grader context-selection probe failed")
manifest = {name: hashlib.sha256(name.encode()).hexdigest() for name in selected}
if json.loads(json.dumps(manifest, sort_keys=True)) != manifest:
    raise SystemExit("grader context manifest JSON/hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, substantive_prose, workspace_redline_violations)):
    raise SystemExit("grader build-context oracle API import probe failed")
print(json.dumps({"python3": "3.10", "fnmatch": "passed", "sha256": "passed", "json": "passed", "yaml": "passed"}, sort_keys=True))
