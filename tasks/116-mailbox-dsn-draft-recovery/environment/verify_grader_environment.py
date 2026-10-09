#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from email import policy
from email.parser import BytesParser

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

raw = b"Content-Type: message/delivery-status\r\n\r\nOriginal-Message-ID: <m1@example.test>\r\nAction: failed\r\nStatus: 5.1.1\r\n"
message = BytesParser(policy=policy.default).parsebytes(raw)
part = next(item for item in message.walk() if item.get_content_type() == "message/delivery-status")
blocks = part.get_payload()
if not isinstance(blocks, list) or blocks[0].get("Status") != "5.1.1":
    raise SystemExit("grader DSN parser probe failed")

connection = sqlite3.connect(":memory:")
try:
    connection.execute("CREATE TABLE drafts(draft_id TEXT PRIMARY KEY, status TEXT)")
    connection.execute("INSERT INTO drafts VALUES(?, ?)", ("draft-1", "pending_review"))
    row = connection.execute("SELECT draft_id, status FROM drafts").fetchone()
finally:
    connection.close()
if row != ("draft-1", "pending_review"):
    raise SystemExit("grader SQLite mail-state probe failed")
if len(hashlib.sha256(json.dumps({"message_id": "m1"}, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader semantic-state hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        substantive_prose,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "mime_delivery_status": "passed", "sqlite": sqlite3.sqlite_version, "yaml": "passed"},
        sort_keys=True,
    )
)
