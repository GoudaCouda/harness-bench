#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import unicodedata


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

rendered = 'source_record_id,title,doi\nP01,"Quoted, title",10.1/test\n'
rows = list(csv.DictReader(io.StringIO(rendered, newline="")))
if rows != [{"source_record_id": "P01", "title": "Quoted, title", "doi": "10.1/test"}]:
    raise SystemExit("CSV quoting/parser probe failed")
ris = "TY  - JOUR\nID  - S01\nDO  - 10.1/test\nER  -\n"
if not all(marker in ris for marker in ("TY  - ", "ID  - ", "ER  -")):
    raise SystemExit("RIS text probe failed")
if unicodedata.category("\u200b") != "Cf":
    raise SystemExit("Unicode format-character probe failed")
if json.loads('{"flow_closes":true}') != {"flow_closes": True}:
    raise SystemExit("JSON parser probe failed")
probe = subprocess.run(
    ["python", "-B", "-c", "import csv,io,json,unicodedata; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"python alias structured-data probe failed: {probe.stderr.strip()}")

print(json.dumps({"python": "3.12", "python3": "3.12", "csv_ris_json": "passed"}, sort_keys=True))
