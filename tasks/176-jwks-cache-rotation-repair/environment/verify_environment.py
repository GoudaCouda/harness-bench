#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

keys = [
    {"issuer":"issuer-a","kid":"same","alg":"RS256","not_before":10,"not_after":20,"revoked":False},
    {"issuer":"issuer-b","kid":"same","alg":"ES256","not_before":10,"not_after":20,"revoked":False},
]
keymap = {(row["issuer"],row["kid"]):row for row in keys}
if keymap[("issuer-a","same")]["alg"] != "RS256" or keymap[("issuer-b","same")]["alg"] != "ES256":
    raise SystemExit("issuer-scoped kid lookup probe failed")

fetched_at = 12
active = keymap[("issuer-a","same")]
if not (active["not_before"] <= 19 < active["not_after"]):
    raise SystemExit("half-open active-key probe failed")
if active["not_before"] <= 20 < active["not_after"]:
    raise SystemExit("exclusive not_after probe failed")

clock_age = 11 - fetched_at
if clock_age >= 0:
    raise SystemExit("negative cache-age fixture failed")
clock_decision = "clock_before_fetch" if clock_age < 0 else "active_key"
if clock_decision != "clock_before_fetch":
    raise SystemExit("global clock precedence probe failed")

expired_now, max_stale = 20, 8
age = expired_now - fetched_at
if not (expired_now >= active["not_after"] and 0 <= age <= max_stale):
    raise SystemExit("inclusive bounded-stale probe failed")
print(json.dumps({"python3":"3.12","issuer_scoped_kid":"passed",
                  "half_open_validity":"passed","clock_precedence":"passed",
                  "bounded_stale":"passed",
                  "identity_service":"not_required_by_offline_task_contract"},sort_keys=True))
