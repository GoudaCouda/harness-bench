#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import observation, sources_unchanged, substantive_prose, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-logrotate-grader-probe-") as temporary:
    source = Path(temporary) / "source"
    copied = Path(temporary) / "copied"
    source.mkdir()
    (source / "service.log").write_text('{"record_id":"r1"}\n', encoding="utf-8")
    shutil.copytree(source, copied)
    if copied.joinpath("service.log").stat().st_size != source.joinpath("service.log").stat().st_size:
        raise SystemExit("grader writable-copy stat probe failed")
    completed = subprocess.run(["python3", "-c", "import json;print(json.dumps([]))"], text=True, capture_output=True, timeout=5)
    if completed.returncode != 0 or json.loads(completed.stdout) != []:
        raise SystemExit("grader replay subprocess/JSON probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, substantive_prose, workspace_redline_violations)):
    raise SystemExit("grader tailer oracle API import probe failed")
print(json.dumps({"python3": "3.10", "stat": "passed", "writable_copy": "passed", "subprocess": "passed", "yaml": "passed"}, sort_keys=True))
