#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

lines = ['{"user_id":"u1","stage":"signup","timestamp":"2026-01-01T00:01:00Z"}', '{"user_id":"u1","stage":"visit","timestamp":"2026-01-01T00:00:00Z"}']
events = [json.loads(line) for line in lines]
if len(events) != 2:
    raise SystemExit("JSONL parsing probe failed")

ordered = sorted(events, key=lambda row: datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")))
if [row["stage"] for row in ordered] != ["visit", "signup"]:
    raise SystemExit("event-time ordering probe failed")

bot_users = {row["user_id"] for row in [{"user_id": "u2", "user_agent": "SyntheticBot/1"}] if any(token in row["user_agent"].casefold() for token in ("bot", "crawler", "synthetic"))}
if bot_users != {"u2"}:
    raise SystemExit("whole-user bot exclusion probe failed")

stages = ("visit", "signup", "verify_email", "trial_start", "purchase")
reached = [stage for stage in stages if stage in {row["stage"] for row in ordered}]
if reached != ["visit", "signup"]:
    raise SystemExit("ordered funnel-stage probe failed")

print(json.dumps({"python3": "3.12", "jsonl": "passed", "event_time": "passed", "bot_filter": "passed"}, sort_keys=True))
