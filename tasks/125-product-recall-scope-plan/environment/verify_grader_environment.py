#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import sqlite3
import sys

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

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
    raise SystemExit("grader genealogy traversal probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE inventory(lot TEXT PRIMARY KEY, on_hand INTEGER, quarantined INTEGER)")
    connection.execute("INSERT INTO inventory VALUES('LOT-A', 20, 20)")
    row = connection.execute("SELECT on_hand, quarantined FROM inventory").fetchone()
finally:
    connection.close()
if row != (20, 20):
    raise SystemExit("grader recall inventory SQLite probe failed")
if len(hashlib.sha256(json.dumps(sorted(seen)).encode()).hexdigest()) != 64:
    raise SystemExit("grader semantic-plan hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases, bounded_text_semantic_input, explicit_external_action_claims,
        observation, read_json_object, sources_unchanged,
        substantive_prose, workspace_redline_violations,
    )
):
    raise SystemExit("grader recall oracle API import probe failed")

print(json.dumps({"python3": "3.10", "genealogy": "passed", "sqlite": sqlite3.sqlite_version, "sha256": "passed", "yaml": "passed"}, sort_keys=True))
