#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

counts = Counter(("evt-2", "evt-1", "evt-2"))
if sorted(key for key, count in counts.items() if count > 1) != ["evt-2"]:
    raise SystemExit("grader webhook deduplication probe failed")
if datetime.fromisoformat("2026-08-18T12:00:00+00:00").astimezone(timezone.utc).hour != 12:
    raise SystemExit("grader UTC event-time probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE events(sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE)")
    connection.execute("INSERT INTO events VALUES(?, ?)", (1, "evt-1"))
    row = connection.execute("SELECT sequence, event_id FROM events").fetchone()
finally:
    connection.close()
if row != (1, "evt-1"):
    raise SystemExit("grader SQLite probe failed")
if len(hashlib.sha256(json.dumps({"event": "evt-1"}, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader evidence hash probe failed")
if re.fullmatch(r"evt-[0-9]+", "evt-2") is None:
    raise SystemExit("grader event-id regex probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        bounded_text_semantic_input,
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "jsonl_event_replay": "passed", "datetime_utc": "passed", "sqlite": sqlite3.sqlite_version},
        sort_keys=True,
    )
)
