#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import subprocess
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

state = {"revision": 4, "services": {"billing-api": {"truststore": ["root-2024", "root-2026"]}}}
digest = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if len(digest) != 64:
    raise SystemExit("canonical state digest probe failed")
if datetime.fromisoformat("2027-08-01T00:00:00+00:00") <= datetime.fromisoformat("2026-08-16T12:00:00+00:00"):
    raise SystemExit("certificate validity datetime probe failed")
probe = subprocess.run(
    ["python3", "-B", "-c", "import argparse,datetime,hashlib,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"python3 PKI controller probe failed: {probe.stderr.strip()}")

print(json.dumps({"python3": "3.12", "datetime": "passed", "sha256": "passed"}, sort_keys=True))
