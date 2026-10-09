#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
with tempfile.TemporaryDirectory(prefix="hb-logrotate-probe-") as temporary:
    root = Path(temporary)
    rotated = root / "service.log.1"
    active = root / "service.log"
    rotated.write_text('{"record_id":"r1"}\n{"record_id":"r2"}\n', encoding="utf-8")
    active.write_text('{"record_id":"r2"}\n{"record_id":"r3"}\n', encoding="utf-8")
    old_stat = rotated.stat()
    new_stat = active.stat()
    if old_stat.st_ino == new_stat.st_ino or old_stat.st_dev != new_stat.st_dev:
        raise SystemExit("rotated file identity probe failed")
    records = [json.loads(line) for path in (rotated, active) for line in path.read_text().splitlines()]
    seen = set()
    delta = [row["record_id"] for row in records if not (row["record_id"] in seen or seen.add(row["record_id"]))]
    if delta != ["r1", "r2", "r3"]:
        raise SystemExit("JSONL duplicate suppression probe failed")
    staged = root / ".checkpoint.tmp"
    final = root / "checkpoint.json"
    staged.write_text(json.dumps({"device": new_stat.st_dev, "inode": new_stat.st_ino, "byte_offset": new_stat.st_size}) + "\n", encoding="utf-8")
    os.replace(staged, final)
    checkpoint = json.loads(final.read_text(encoding="utf-8"))
    if checkpoint["byte_offset"] != active.stat().st_size:
        raise SystemExit("EOF checkpoint atomic replace probe failed")
print(json.dumps({"python3": "3.12", "inode_identity": "passed", "jsonl_dedup": "passed", "atomic_checkpoint": "passed"}, sort_keys=True))
