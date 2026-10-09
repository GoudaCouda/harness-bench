#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

payload = b"HARNESSBENCH-RECORD-TRANSFER-PROBE\n"
expected = hashlib.sha256(payload).hexdigest()
with tempfile.TemporaryDirectory(prefix="hb006-env-") as directory:
    root = Path(directory)
    source = root / "source/records/probe.bin"
    staged = root / "staged/records/REC-PROBE/probe.bin"
    source.parent.mkdir(parents=True)
    staged.parent.mkdir(parents=True)
    source.write_bytes(payload)
    shutil.copyfile(source, staged)
    first = hashlib.sha256(staged.read_bytes()).hexdigest()
    shutil.copyfile(source, staged)
    second = hashlib.sha256(staged.read_bytes()).hexdigest()

if first != expected or second != expected:
    raise SystemExit("deterministic copy and SHA-256 staging probe failed")
print(json.dumps({"python": "3.12", "sha256": expected, "idempotent_copy": first == second}, sort_keys=True))
