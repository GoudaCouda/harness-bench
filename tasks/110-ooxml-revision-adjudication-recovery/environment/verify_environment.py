#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

with tempfile.TemporaryDirectory(prefix="hb-ooxml-probe-") as temporary:
    root = Path(temporary)
    package = root / "probe.docx"
    xml = b'<w:document xmlns:w="urn:probe"><w:body><w:p><w:r><w:t>ok</w:t></w:r></w:p></w:body></w:document>'
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", xml)
    with zipfile.ZipFile(package) as archive:
        parsed = ET.fromstring(archive.read("word/document.xml"))
        if set(archive.namelist()) != {"[Content_Types].xml", "word/document.xml"}:
            raise SystemExit("OOXML ZIP package probe failed")
    if not parsed.tag.endswith("document"):
        raise SystemExit("OOXML XML parser probe failed")

    database = root / "review_state.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE journal(sequence INTEGER PRIMARY KEY, change_id TEXT UNIQUE);"
            "INSERT INTO journal VALUES(1, 'CH-01');"
            "COMMIT;"
        )
        row = connection.execute("SELECT sequence, change_id FROM journal").fetchone()
    finally:
        connection.close()
    if row != (1, "CH-01"):
        raise SystemExit("SQLite durable journal probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "zip_deflate": "passed",
            "xml": "passed",
            "sqlite_transaction": "passed",
        },
        sort_keys=True,
    )
)
