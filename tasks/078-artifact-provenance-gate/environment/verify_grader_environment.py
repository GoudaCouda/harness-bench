#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys

import yaml

from harnessbench.grading.task_checks import explicit_external_action_claims, sources_unchanged

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("link,status\ntag_commit,pass\n")))
if rows != [{"link": "tag_commit", "status": "pass"}]:
    raise SystemExit("CSV parser probe failed")
probe = subprocess.run(
    [sys.executable, "-B", "-c", "import argparse,csv,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"controller subprocess probe failed: {probe.stderr!r}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not callable(explicit_external_action_claims) or not callable(sources_unchanged):
    raise SystemExit("task-check API import probe failed")

print(json.dumps({"python3": "3.10", "csv": "passed", "subprocess": "passed", "yaml": "passed"}, sort_keys=True))
