#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    workspace_redline_violations,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
dataset = {"PatientIdentityRemoved": "YES", "SOPInstanceUID": "2.25.141"}
payload = b"\0" * 128 + b"DICM" + json.dumps(dataset, sort_keys=True).encode()
if json.loads(payload[132:]) != dataset or len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("grader DICOM framing/hash probe failed")
with tempfile.TemporaryDirectory(prefix="hb-dicom-grader-probe-") as temporary:
    database = Path(temporary) / "imaging.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE exports(uid TEXT PRIMARY KEY, status TEXT)")
        connection.executemany(
            "INSERT INTO exports VALUES (?, ?)",
            [("2.25.1", "protected"), ("2.25.2", "locally_deidentified")],
        )
        connection.commit()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT uid,status FROM exports ORDER BY uid").fetchall()
    if rows != [("2.25.1", "protected"), ("2.25.2", "locally_deidentified")]:
        raise SystemExit("grader DICOM SQLite read-only probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    workspace_redline_violations,
)):
    raise SystemExit("grader DICOM oracle API import probe failed")
print(json.dumps({
    "python3": "3.10",
    "dicm_framing": "passed",
    "sha256": "passed",
    "sqlite": "passed",
    "yaml": "passed",
}, sort_keys=True))
