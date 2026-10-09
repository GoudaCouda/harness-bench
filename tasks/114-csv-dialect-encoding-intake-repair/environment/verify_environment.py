#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

raw = b"\xef\xbb\xbfname,note\r\nAda,\"a,b\"\r\n"
text = raw.decode("utf-8-sig")
rows = list(csv.reader(io.StringIO(text), delimiter=","))
if rows != [["name", "note"], ["Ada", "a,b"]]:
    raise SystemExit("UTF-8 BOM/quoted CSV probe failed")

utf16 = b"\xff\xfe" + "a;b\r\n1;2\r\n".encode("utf-16-le")
if utf16.decode("utf-16").splitlines() != ["a;b", "1;2"]:
    raise SystemExit("UTF-16 LE/CRLF probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "utf8_bom": "passed",
            "utf16_le": "passed",
            "csv_quoted_fields": "passed",
        },
        sort_keys=True,
    )
)
