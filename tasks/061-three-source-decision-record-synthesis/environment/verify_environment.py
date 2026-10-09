#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import date

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

emails = [
    {
        "id": "email-004",
        "date": "2026-04-25",
        "body": "Decision update: launch date moves to July 15, 2026.",
    }
]
decoded = json.loads(json.dumps(emails, sort_keys=True))
if decoded[0]["id"] != "email-004" or date.fromisoformat(decoded[0]["date"]) != date(2026, 4, 25):
    raise SystemExit("email decision/date probe failed")

buf = io.StringIO(newline="")
writer = csv.DictWriter(
    buf,
    fieldnames=[
        "decision_key",
        "winning_source",
        "superseded_sources",
        "resolution_reason",
        "priority_rule",
    ],
)
writer.writeheader()
writer.writerow(
    {
        "decision_key": "launch_date",
        "winning_source": "email/thread.json#email-004",
        "superseded_sources": "meeting/meeting_transcript.md#MT-1",
        "resolution_reason": "later decision supersedes meeting proposal",
        "priority_rule": "later decision email",
    }
)
rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
if len(rows) != 1 or rows[0]["decision_key"] != "launch_date":
    raise SystemExit("source-conflict CSV round-trip probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "email_json": "passed",
            "iso_dates": "passed",
            "csv_conflicts": "passed",
        },
        sort_keys=True,
    )
)
