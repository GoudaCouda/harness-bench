#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import subprocess
import sys

import yaml

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = {"spec": {"ports": [{"targetPort": "http"}]}}
clone = copy.deepcopy(source)
clone["spec"]["ports"][0]["targetPort"] = "web"
if source["spec"]["ports"][0]["targetPort"] != "http":
    raise SystemExit("deep-copy isolation probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("YAML probe failed")
if not all(callable(value) for value in (explicit_external_action_claims, observation, sources_unchanged)):
    raise SystemExit("grader task-check API import probe failed")
if not callable(subprocess.run) or json.loads('{"ok":true}') != {"ok": True}:
    raise SystemExit("grader stdlib probe failed")

print(json.dumps({"python3": "3.10", "yaml": "passed", "grader_api": "passed"}, sort_keys=True))
