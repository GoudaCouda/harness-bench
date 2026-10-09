#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

instant = datetime.fromisoformat("2026-05-12T11:00:00-04:00")
expected = {
    "America/New_York": "2026-05-12T11:00:00-04:00",
    "America/Chicago": "2026-05-12T10:00:00-05:00",
    "Europe/London": "2026-05-12T16:00:00+01:00",
    "America/Sao_Paulo": "2026-05-12T12:00:00-03:00",
}
observed = {zone: instant.astimezone(ZoneInfo(zone)).isoformat() for zone in expected}
if observed != expected:
    raise SystemExit(f"IANA time-zone conversion probe failed: {observed}")
print(json.dumps({"python": "3.12", "zoneinfo": observed}, sort_keys=True))
