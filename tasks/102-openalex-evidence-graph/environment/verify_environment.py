#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

rows = list(csv.DictReader(io.StringIO("work_id,status,evidence_refs\nW1,canonical,works_page1.json#W1\n")))
if rows[0]["work_id"] != "W1" or rows[0]["status"] != "canonical":
    raise SystemExit("graph CSV parser probe failed")
state = {"pages": {"3": "declared_not_found", "4": "consumed"}, "external_actions_executed": False}
digest = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if len(digest) != 64:
    raise SystemExit("graph state digest probe failed")
probe = subprocess.run(
    ["python3", "-B", "-c", "import argparse,csv,hashlib,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"python3 graph controller probe failed: {probe.stderr.strip()}")

print(json.dumps({"python3": "3.12", "csv_json": "passed", "sha256": "passed"}, sort_keys=True))
