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
    connection.execute("CREATE TABLE accounts (id TEXT PRIMARY KEY, version INTEGER)")
    connection.execute("CREATE TABLE journal (id TEXT PRIMARY KEY, before_json TEXT, restored INTEGER)")
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("INSERT INTO accounts VALUES ('svc-probe', 1)")
    before = json.dumps({"id": "svc-probe", "version": 1}, sort_keys=True)
    connection.execute("INSERT INTO journal VALUES ('J-PROBE', ?, 0)", (before,))
    connection.commit()
    if connection.execute("SELECT version FROM accounts WHERE id='svc-probe'").fetchone() != (1,):
        raise SystemExit("SQLite recovery transaction probe failed")

digest = hashlib.sha256((json.dumps({"version": 1}, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
if len(digest) != 64:
    raise SystemExit("canonical SHA-256 probe failed")
probe = subprocess.run(
    ["python3", "-B", "-c", "import hashlib,json,pathlib,sqlite3; print(sqlite3.sqlite_version)"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or not probe.stdout.strip():
    raise SystemExit(f"python3 SQLite subprocess probe failed: {probe.stderr.strip()}")

print(json.dumps({"python3": "3.12", "sqlite": sqlite3.sqlite_version, "sha256": "passed"}, sort_keys=True))
