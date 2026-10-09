#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sqlite3
import sys
import zipfile
from xml.etree import ElementTree as ET

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("word/document.xml", "<document><p>ok</p></document>")
with zipfile.ZipFile(buffer) as archive:
    root = ET.fromstring(archive.read("word/document.xml"))
if root.tag != "document":
    raise SystemExit("grader OOXML ZIP/XML probe failed")
connection = sqlite3.connect(":memory:")
try:
    connection.executescript(
        "CREATE TABLE journal(sequence INTEGER PRIMARY KEY, change_id TEXT UNIQUE);"
        "INSERT INTO journal VALUES(1, 'CH-01');"
    )
    row = connection.execute("SELECT change_id FROM journal").fetchone()
finally:
    connection.close()
if row != ("CH-01",):
    raise SystemExit("grader SQLite probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        bounded_text_semantic_input,
        explicit_external_action_claims,
        observation,
        read_json_object,
        sources_unchanged,
        substantive_prose,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "zip_deflate": "passed",
            "xml": "passed",
            "sqlite": sqlite3.sqlite_version,
        },
        sort_keys=True,
    )
)
