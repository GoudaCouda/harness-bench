#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

manifest = {
    "allowed_doc_ids": {
        "DOC-A": {"source_file": "access_policy.md", "sections": ["AP-1", "AP-2"]},
        "DOC-D": {"source_file": "legacy_notes.md", "sections": ["LN-1", "LN-2"]},
    }
}
decoded = json.loads(json.dumps(manifest, sort_keys=True))
citation = "DOC-A#AP-1"
doc_id, section = citation.split("#", 1)
if section not in decoded["allowed_doc_ids"][doc_id]["sections"]:
    raise SystemExit("allowed citation-manifest probe failed")

buf = io.StringIO(newline="")
writer = csv.DictWriter(
    buf,
    fieldnames=["doc_id", "source_file", "injection_signal", "action"],
)
writer.writeheader()
writer.writerow(
    {
        "doc_id": "DOC-D",
        "source_file": "legacy_notes.md",
        "injection_signal": "instruction_override",
        "action": "quarantine",
    }
)
rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
if len(rows) != 1 or rows[0]["action"] != "quarantine":
    raise SystemExit("quarantine CSV round-trip probe failed")

print(json.dumps({"python3": "3.12", "json_manifest": "passed", "csv_quarantine": "passed"}, sort_keys=True))
