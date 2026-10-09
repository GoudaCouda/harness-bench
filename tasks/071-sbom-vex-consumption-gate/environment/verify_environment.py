#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

root = Path("/workspace").resolve()
candidate = (root / "work/decision_ledger.json").resolve()
if not candidate.is_relative_to(root):
    raise SystemExit("workspace-relative path containment probe failed")

stamp = datetime.fromisoformat("2026-08-17T12:00:00+00:00").astimezone(timezone.utc)
if stamp.isoformat() != "2026-08-17T12:00:00+00:00":
    raise SystemExit("timezone-aware freshness probe failed")

payload = json.dumps({"release_id": "REL-PROBE", "rows": [2, 1]}, sort_keys=True, separators=(",", ":")).encode()
digest = hashlib.sha256(payload).hexdigest()
if len(digest) != 64:
    raise SystemExit("canonical JSON digest probe failed")

probe = subprocess.run(
    [sys.executable, "-c", "import argparse,hashlib,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"controller subprocess probe failed: {probe.stdout!r} {probe.stderr!r}")

print(json.dumps({"python3": "3.12", "path_containment": "passed", "datetime": "passed", "sha256_json": "passed", "subprocess": "passed"}, sort_keys=True))
