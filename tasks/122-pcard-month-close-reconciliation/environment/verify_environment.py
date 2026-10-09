#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


class ReceiptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)


parser = ReceiptParser()
parser.feed("<html><body>Transaction PC-203 total $260.00</body></html>")
if "PC-203" not in " ".join(parser.text):
    raise SystemExit("HTML receipt parsing probe failed")

with tempfile.TemporaryDirectory(prefix="hb-pcard-probe-") as temporary:
    root = Path(temporary)
    database = root / "pcard_close_state.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN; CREATE TABLE close_journal(close_id TEXT PRIMARY KEY, phase TEXT); INSERT INTO close_journal VALUES('PCLOSE-1', 'committed'); COMMIT;"
        )
        row = connection.execute("SELECT close_id, phase FROM close_journal").fetchone()
    finally:
        connection.close()
    readonly = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        reread = readonly.execute("SELECT close_id, phase FROM close_journal").fetchone()
    finally:
        readonly.close()
    pdf = b"%PDF-1.4\nSynthetic local purchase-card receipt\n%%EOF\n"
    if not pdf.startswith(b"%PDF-") or b"receipt" not in pdf:
        raise SystemExit("local PDF receipt-byte probe failed")
    if row != ("PCLOSE-1", "committed") or reread != row:
        raise SystemExit("SQLite close transaction/read-only replay probe failed")
    if len(hashlib.sha256(pdf + database.read_bytes()).hexdigest()) != 64:
        raise SystemExit("receipt and close-state hash probe failed")

print(json.dumps({"python3": "3.12", "sqlite": sqlite3.sqlite_version, "html": "passed", "pdf_bytes": "passed", "sha256": "passed"}, sort_keys=True))
