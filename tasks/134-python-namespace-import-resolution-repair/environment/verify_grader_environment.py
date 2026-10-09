#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import observation, sources_unchanged, substantive_prose, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-namespace-grader-probe-") as temporary:
    root = Path(temporary)
    first = root / "first/acme/plugins"
    second = root / "second/acme/plugins"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "one.py").write_text("VALUE=1\n", encoding="utf-8")
    (second / "two.py").write_text("VALUE=2\n", encoding="utf-8")
    command = "import sys;sys.path[:0]=" + repr([str(first.parents[1]), str(second.parents[1])]) + ";import acme.plugins.one as a,acme.plugins.two as b;print(a.VALUE+b.VALUE)"
    completed = subprocess.run([sys.executable, "-I", "-c", command], text=True, capture_output=True, timeout=5)
    if completed.returncode != 0 or completed.stdout.strip() != "3":
        raise SystemExit("grader independent namespace import probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, substantive_prose, workspace_redline_violations)):
    raise SystemExit("grader namespace oracle API import probe failed")
print(json.dumps({"python3": "3.10", "pep420": "passed", "subprocess": "passed", "yaml": "passed"}, sort_keys=True))
