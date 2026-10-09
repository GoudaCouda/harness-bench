#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import sys

from harnessbench.grading.legacy_case_adapter import grouped_observations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

rows = list(
    csv.DictReader(
        io.StringIO(
            "doc_id,source_file,injection_signal,action\n"
            "DOC-D,legacy_notes.md,instruction_override,quarantine\n"
        )
    )
)
if rows[0]["doc_id"] != "DOC-D":
    raise SystemExit("grader CSV probe failed")
if not re.search(r"\bquarantin\w*\b", rows[0]["action"], re.IGNORECASE):
    raise SystemExit("quarantine relation probe failed")

private = {"checks": [{"id": "audit_explains_isolation", "pass": True}]}
observed = grouped_observations(private, {"isolation_audit": ["audit_explains_isolation"]})
if not observed["isolation_audit"]["pass"]:
    raise SystemExit("legacy case adapter probe failed")

print(json.dumps({"python3": "3.10", "csv_regex": "passed", "case_adapter": "passed"}, sort_keys=True))
