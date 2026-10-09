#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


def version(value: str) -> tuple[int, int, int]:
    parts = tuple(int(part) for part in value.split("."))
    if len(parts) != 3:
        raise SystemExit("synthetic semantic-version probe failed")
    return parts


choices = list(itertools.product(("4.8.0", "4.9.0"), ("2.2.0", "2.3.0")))
viable = [pair for pair in choices if version(pair[0]) >= (4, 9, 0) and version(pair[1]) >= (2, 3, 0)]
if viable != [("4.9.0", "2.3.0")]:
    raise SystemExit("dependency-product/version-constraint probe failed")

payload = (json.dumps({"layers": ["base", "app"], "schemaVersion": 2}, sort_keys=True, separators=(",", ":")) + "\n").encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("content-addressing probe failed")

with tempfile.TemporaryDirectory(prefix="hb-oci-probe-") as temporary:
    root = Path(temporary)
    destination = root / "dist"
    staging = root / ".build"
    staging.mkdir()
    (staging / "manifest.json").write_bytes(payload)
    os.replace(staging, destination)
    if (destination / "manifest.json").read_bytes() != payload:
        raise SystemExit("atomic OCI artifact staging probe failed")
    shutil.rmtree(destination)

print(
    json.dumps(
        {
            "python3": "3.12",
            "dependency_graph": "passed",
            "sha256": "passed",
            "atomic_directory_replace": "passed",
        },
        sort_keys=True,
    )
)
