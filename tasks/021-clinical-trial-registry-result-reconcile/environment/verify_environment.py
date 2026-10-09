#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
payload = {"trial_id": "NCT-SYN-21021", "state": "under_qc_not_posted"}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
digest = hashlib.sha256(canonical).hexdigest()
if len(digest) != 64:
    raise SystemExit("canonical SHA-256 probe failed")
completed = subprocess.run(
    ["python3", "-c", "import argparse; p=argparse.ArgumentParser(); p.add_argument('command'); print(p.parse_args(['replay']).command)"],
    capture_output=True, text=True, check=False, timeout=10,
)
if completed.returncode != 0 or completed.stdout.strip() != "replay":
    raise SystemExit(f"controller CLI probe failed: {completed.stderr!r}")
print(json.dumps({
    "python3": "3.12",
    "canonical_sha256": digest,
    "controller_cli": "passed",
}, sort_keys=True))
