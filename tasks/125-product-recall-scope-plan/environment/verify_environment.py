#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

feed = [json.loads(line) for line in ['{"event_id":"EV-2","sequence":20}', '{"event_id":"EV-1","sequence":10}', '{"event_id":"EV-2","sequence":20}']]
unique = {row["event_id"]: row for row in feed}
ordered = sorted(unique.values(), key=lambda row: row["sequence"])
if [row["event_id"] for row in ordered] != ["EV-1", "EV-2"]:
    raise SystemExit("at-least-once recall feed ordering/dedup probe failed")

graph: dict[str, list[str]] = defaultdict(list, {"CB-ROOT": ["CB-CHILD"], "CB-CHILD": ["LOT-E"]})
seen = {"CB-ROOT"}
queue = ["CB-ROOT"]
while queue:
    parent = queue.pop(0)
    for child in graph[parent]:
        if child not in seen:
            seen.add(child)
            queue.append(child)
if "LOT-E" not in seen:
    raise SystemExit("recall genealogy traversal probe failed")

with tempfile.TemporaryDirectory(prefix="hb-recall-probe-") as temporary:
    database = Path(temporary) / "recall.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "CREATE TABLE inventory(lot TEXT PRIMARY KEY, on_hand INTEGER, available INTEGER, quarantined INTEGER); INSERT INTO inventory VALUES('LOT-A', 20, 20, 0);"
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE inventory SET available=0, quarantined=20 WHERE lot='LOT-A'")
        connection.commit()
        row = connection.execute("SELECT on_hand, available, quarantined FROM inventory").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT available, quarantined FROM inventory").fetchone()
    finally:
        readonly.close()
    if row != (20, 0, 20) or reread != (0, 20):
        raise SystemExit("SQLite recall transaction/read-only replay probe failed")
    if sum(row[1:]) != row[0]:
        raise SystemExit("recall inventory conservation probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("recall state hash probe failed")

print(json.dumps({"python3": "3.12", "jsonl_dedup": "passed", "genealogy": "passed", "sqlite": sqlite3.sqlite_version, "conservation": "passed", "sha256": "passed"}, sort_keys=True))
