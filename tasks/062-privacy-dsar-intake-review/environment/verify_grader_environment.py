#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata

import yaml
from harnessbench.grading.structured_io import (
    markdown_visible_text,
    spreadsheet_formula_text,
)

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

visible = markdown_visible_text("**No** requester [message](draft.md) was sent.")
if "No requester message was sent." not in visible:
    raise SystemExit("Markdown visible-text probe failed")
if not spreadsheet_formula_text("=HYPERLINK(\"https://example.test\")"):
    raise SystemExit("spreadsheet formula probe failed")

normalized = unicodedata.normalize("NFKC", "Maya\u200b Chen").replace("\u200b", "")
if not re.search(r"maya\s+chen", normalized, re.IGNORECASE):
    raise SystemExit("Unicode identity normalization probe failed")

payload = yaml.safe_load("gate: true\nweight: 0.0\n")
digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
if len(digest) != 64 or payload != {"gate": True, "weight": 0.0}:
    raise SystemExit("grader YAML/hash probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "structured_io": "passed",
            "formula_guard": "passed",
            "unicode_identity": "passed",
            "yaml_hash": "passed",
        },
        sort_keys=True,
    )
)
