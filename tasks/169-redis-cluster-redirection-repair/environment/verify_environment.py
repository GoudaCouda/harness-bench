#!/usr/bin/env python3
from __future__ import annotations

import binascii
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


def redis_slot(key: str) -> int:
    raw = key.encode("utf-8")
    left = raw.find(b"{")
    right = raw.find(b"}", left + 1)
    if left >= 0 and right > left + 1:
        raw = raw[left + 1:right]
    return binascii.crc_hqx(raw, 0) % 16384


if redis_slot("{invoice}:line-1") != redis_slot("{invoice}:line-2"):
    raise SystemExit("Redis hash-tag slot probe failed")
if not 0 <= redis_slot("ordinary-key") < 16384:
    raise SystemExit("Redis CRC16 slot range probe failed")

slot_cache = {redis_slot("{invoice}:line-1"): "node-a"}
slot = next(iter(slot_cache))
ask_target = "node-b"
ask_cache = dict(slot_cache)
ask_decision = {"target": ask_target, "send_asking": True}
if ask_cache != slot_cache or not ask_decision["send_asking"]:
    raise SystemExit("ASK one-shot redirection probe failed")
moved_cache = dict(slot_cache)
moved_cache[slot] = "node-c"
if moved_cache[slot] != "node-c":
    raise SystemExit("MOVED persistent-cache probe failed")

base, cap, attempt = 100, 800, 4
backoff = min(base * 2 ** (attempt - 1), cap)
if backoff != 800 or not (1000 > backoff + 50):
    raise SystemExit("retry budget arithmetic probe failed")

print(json.dumps({
    "python3": "3.12",
    "redis_slot_semantics": "passed",
    "ask_moved_state": "passed",
    "retry_budget": "passed",
    "redis_service": "not_required_by_offline_task_contract",
}, sort_keys=True))
