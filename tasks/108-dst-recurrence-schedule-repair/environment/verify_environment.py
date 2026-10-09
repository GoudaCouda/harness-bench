#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

zones = ("UTC", "America/New_York", "Europe/Berlin", "Australia/Lord_Howe")
try:
    loaded = {name: ZoneInfo(name) for name in zones}
except ZoneInfoNotFoundError as exc:
    raise SystemExit(f"IANA timezone database is incomplete: {exc}") from exc

gap_candidate = datetime(2026, 3, 8, 2, 30, tzinfo=loaded["America/New_York"])
fold_early = datetime(
    2026, 11, 1, 1, 30, tzinfo=loaded["America/New_York"], fold=0
)
fold_late = fold_early.replace(fold=1)
if fold_early.astimezone(timezone.utc) == fold_late.astimezone(timezone.utc):
    raise SystemExit("PEP 495 fold resolution probe failed")
if gap_candidate.tzinfo is None:
    raise SystemExit("timezone attachment probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "zoneinfo": list(zones),
            "pep495_fold": "passed",
        },
        sort_keys=True,
    )
)
