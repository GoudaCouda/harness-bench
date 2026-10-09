#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

with tempfile.TemporaryDirectory(prefix="hb-dms-probe-") as temporary:
    root = Path(temporary)
    source = root / "assets" / "survey.csv"
    source.parent.mkdir()
    source.write_bytes(b"participant,value\np01,7\n")
    staging = root / "next" / "repository"
    staging.mkdir(parents=True)
    copied = staging / source.name
    shutil.copyfile(source, copied)
    if source.read_bytes() != copied.read_bytes():
        raise SystemExit("byte-exact staging copy probe failed")
    digest = hashlib.sha256(copied.read_bytes()).hexdigest()
    rows = list(csv.DictReader(io.StringIO(copied.read_text())))
    if digest != hashlib.sha256(source.read_bytes()).hexdigest() or rows[0]["participant"] != "p01":
        raise SystemExit("CSV or SHA-256 package probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "csv": "passed",
            "sha256": "passed",
            "atomic_staging_primitives": "passed",
        },
        sort_keys=True,
    )
)
