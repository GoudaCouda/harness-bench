#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

root = Path("/workspace").resolve()
candidate = (root / "repo/config.json").resolve()
if not candidate.is_relative_to(root):
    raise SystemExit("workspace-relative path containment probe failed")

stamp = datetime.fromisoformat("2026-08-17T12:00:00+00:00").astimezone(timezone.utc)
if stamp.isoformat() != "2026-08-17T12:00:00+00:00":
    raise SystemExit("timezone probe failed")

probe = subprocess.run(
    [sys.executable, "-c", "import copy,json,re,pathlib; print(json.dumps({'ok': True}))"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or json.loads(probe.stdout) != {"ok": True}:
    raise SystemExit(f"migration runtime probe failed: {probe.stdout!r} {probe.stderr!r}")

print(json.dumps({"python3": "3.12", "json_subprocess": "passed", "path_datetime": "passed"}, sort_keys=True))
