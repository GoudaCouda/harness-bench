#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
probe = subprocess.run(
    ["python3", "-c", "import json; print(json.dumps({'status':'pass','checks':16}, sort_keys=True))"],
    capture_output=True, text=True, check=False, timeout=10,
)
try:
    report = json.loads(probe.stdout)
except json.JSONDecodeError as exc:
    raise SystemExit(f"python3 CLI emitted invalid JSON: {exc}") from exc
if probe.returncode != 0 or report != {"checks": 16, "status": "pass"}:
    raise SystemExit(f"python3 CLI/subprocess probe failed: {probe.stderr!r}")
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("command", choices=("inspect", "verify"))
if parser.parse_args(["verify"]).command != "verify":
    raise SystemExit("argparse command probe failed")
if re.fullmatch(r"KST-\d{4}-\d{4}", "KST-2025-0821") is None:
    raise SystemExit("review identity regex probe failed")
print(json.dumps({"python3": "3.12", "local_control_cli": "passed"}, sort_keys=True))
