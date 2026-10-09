#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

instant = datetime.fromisoformat("2026-05-12T15:00:00+00:00")
zones = ("America/New_York", "America/Chicago", "Europe/London", "America/Sao_Paulo")
offsets = {}
for zone in zones:
    local = instant.astimezone(ZoneInfo(zone))
    offsets[zone] = local.utcoffset().total_seconds()
    if ZoneInfo(zone).key != zone:
        raise SystemExit(f"zone identity mismatch for {zone}")
if offsets != {"America/New_York": -14400.0, "America/Chicago": -18000.0, "Europe/London": 3600.0, "America/Sao_Paulo": -10800.0}:
    raise SystemExit(f"grader tzdata offset probe failed: {offsets}")
print(json.dumps({"zone_offsets_seconds": offsets}, sort_keys=True))
