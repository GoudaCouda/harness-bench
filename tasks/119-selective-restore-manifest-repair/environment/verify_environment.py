#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


def canonical_path(value: str) -> bool:
    return (
        value.startswith("/")
        and value != "/"
        and not value.endswith("/")
        and "\\" not in value
        and all(part not in ("", ".", "..") for part in value.split("/")[1:])
    )


if not canonical_path("/app/data/a.db") or canonical_path("/app/../secret"):
    raise SystemExit("canonical POSIX restore-path probe failed")
if not "/app/data/a.db".startswith("/app/") or "/apple/data".startswith("/app/"):
    raise SystemExit("segment-aware prefix probe failed")
if re.fullmatch(r"[0-9a-f]{64}", hashlib.sha256(b"snapshot").hexdigest()) is None:
    raise SystemExit("snapshot checksum probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "posix_paths": "passed",
            "segment_prefix": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
