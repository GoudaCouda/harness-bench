#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

with tempfile.TemporaryDirectory(prefix="hb097-env-") as temporary:
    root = Path(temporary)
    events = root / "events.jsonl"
    prefix = b'{"seq":1,"event":"probe"}\n'
    events.write_bytes(prefix)
    events.write_bytes(events.read_bytes() + b'{"seq":2,"event":"verify"}\n')
    if not events.read_bytes().startswith(prefix):
        raise SystemExit("append-only JSONL probe failed")
    state = {"clients": [{"id": "metrics-adapter", "trust": "dual"}]}
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if len(digest) != 64:
        raise SystemExit("canonical digest probe failed")

probe = subprocess.run(
    ["python3", "-B", "-c", "import argparse,hashlib,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"python3 controller subprocess probe failed: {probe.stderr.strip()}")

print(json.dumps({"python3": "3.12", "append_only_jsonl": "passed", "digest": "passed"}, sort_keys=True))
