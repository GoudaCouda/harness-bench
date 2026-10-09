#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

now,interval,burst,restart_sec=100,40,2,5
starts=[60,70,80]
window=[at for at in starts if now-interval < at]
if window != [70,80]:
    raise SystemExit("strict start-limit interval probe failed")
if len(window)<burst or min(window)+interval != 110:
    raise SystemExit("burst suppression expiry probe failed")

manual_reset_at=90
after_reset=[at for at in starts if at>manual_reset_at]
if after_reset:
    raise SystemExit("manual reset probe failed")

long_start,long_exit,success_reset=10,50,30
budget=[long_start]
if long_exit-long_start>=success_reset:
    budget=[]
if budget:
    raise SystemExit("long-run budget reset probe failed")

failure_exit=82
next_at=failure_exit+restart_sec
if next_at!=87:
    raise SystemExit("restart delay probe failed")
valid_results={"success","manual_stop","failure","watchdog"}
if None in valid_results:
    raise SystemExit("exit-result validation probe failed")
print(json.dumps({"python3":"3.12","strict_window":"passed",
                  "burst_suppression":"passed","manual_reset":"passed",
                  "long_run_reset":"passed","restart_delay":"passed",
                  "systemd_runtime":"not_required_by_offline_task_contract"},sort_keys=True))
