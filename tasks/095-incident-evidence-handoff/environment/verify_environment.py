#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

with sqlite3.connect(":memory:") as connection:
    connection.execute("CREATE TABLE journal (id TEXT PRIMARY KEY, payload TEXT)")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("INSERT INTO journal VALUES (?, ?)", ("probe", '{"ok":true}'))
    connection.commit()
    row = connection.execute("SELECT id, payload FROM journal").fetchone()
if row != ("probe", '{"ok":true}'):
    raise SystemExit("SQLite transaction/readback probe failed")

probe = subprocess.run(
    ["python3", "-B", "-c", "import hashlib,json,pathlib,sqlite3; print(hashlib.sha256(json.dumps({'ok':True},sort_keys=True).encode()).hexdigest())"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
expected = hashlib.sha256(json.dumps({"ok": True}, sort_keys=True).encode()).hexdigest()
if probe.returncode != 0 or probe.stdout.strip() != expected:
    raise SystemExit(f"python3 stdlib subprocess probe failed: {probe.stderr.strip()}")

print(json.dumps({"python3": "3.12", "sqlite": sqlite3.sqlite_version, "transaction": "passed"}, sort_keys=True))
