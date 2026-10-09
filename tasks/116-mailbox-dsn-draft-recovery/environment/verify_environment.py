#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from email import policy
from email.parser import BytesParser
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

raw = b"Content-Type: multipart/report; report-type=delivery-status; boundary=b\r\n\r\n--b\r\nContent-Type: text/plain\r\n\r\nfailed\r\n--b\r\nContent-Type: message/delivery-status\r\n\r\nOriginal-Message-ID: <m1@example.test>\r\nFinal-Recipient: rfc822; user@example.test\r\nAction: failed\r\nStatus: 5.1.1\r\n\r\n--b--\r\n"
message = BytesParser(policy=policy.default).parsebytes(raw)
delivery_parts = [part for part in message.walk() if part.get_content_type() == "message/delivery-status"]
if len(delivery_parts) != 1:
    raise SystemExit("MIME delivery-status discovery probe failed")
blocks = delivery_parts[0].get_payload()
if not isinstance(blocks, list) or len(blocks) != 1:
    raise SystemExit("MIME delivery-status block probe failed")
block = blocks[0]
if (block.get("Original-Message-ID"), block.get("Action"), block.get("Status")) != ("<m1@example.test>", "failed", "5.1.1"):
    raise SystemExit("DSN field parsing probe failed")

with tempfile.TemporaryDirectory(prefix="hb-mailops-probe-") as temporary:
    database = Path(temporary) / "mailops.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE journal(tx_id TEXT PRIMARY KEY, status TEXT);"
            "INSERT INTO journal VALUES('tx-1', 'committed');"
            "COMMIT;"
        )
        row = connection.execute("SELECT tx_id, status FROM journal").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT tx_id, status FROM journal").fetchone()
    finally:
        readonly.close()
    if row != ("tx-1", "committed") or reread != row:
        raise SystemExit("SQLite mail journal/read-only replay probe failed")
    if len(hashlib.sha256(database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("mail state hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "mime_delivery_status": "passed",
            "sqlite_transaction": "passed",
            "sha256": "passed",
        },
        sort_keys=True,
    )
)
