#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

import yaml

from harnessbench.grading.task_checks import explicit_external_action_claims, sources_unchanged

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

probe = subprocess.run(
    [sys.executable, "-B", "-c", "import itertools,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"checker subprocess probe failed: {probe.stderr!r}")
manifest = yaml.safe_load("schema_version: 2\npass_threshold: 0.8\n")
if manifest["pass_threshold"] != 0.8:
    raise SystemExit("YAML manifest probe failed")
if not callable(explicit_external_action_claims) or not callable(sources_unchanged):
    raise SystemExit("task-check API import probe failed")

print(json.dumps({"python3": "3.10", "subprocess": "passed", "yaml": "passed"}, sort_keys=True))
