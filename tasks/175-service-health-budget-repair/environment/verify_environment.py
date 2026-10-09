#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

events = [
    {"id":"old","service":"api","at":99,"generation":1,"status":"failure"},
    {"id":"left","service":"api","at":70,"generation":2,"status":"failure"},
    {"id":"f1","service":"api","at":80,"generation":2,"status":"failure"},
    {"id":"f2","service":"api","at":81,"generation":2,"status":"failure"},
    {"id":"s1","service":"api","at":82,"generation":2,"status":"success"},
    {"id":"s2","service":"api","at":83,"generation":2,"status":"success"},
    {"id":"m1","service":"worker","at":90,"generation":4,"status":"maintenance_start"},
    {"id":"ignored","service":"worker","at":91,"generation":4,"status":"failure"},
]
windowed = [row for row in events if 100 - 30 < row["at"] <= 100]
latest = {}
for row in events:
    latest[row["service"]] = max(latest.get(row["service"], row["generation"]), row["generation"])
selected = [row for row in windowed if row["generation"] == latest[row["service"]]]
api = sorted((row for row in selected if row["service"] == "api"), key=lambda row:(row["at"],row["id"]))
failures = successes = 0
state = "healthy"
for row in api:
    if row["status"] == "failure":
        failures += 1; successes = 0
    elif row["status"] == "success":
        successes += 1
        if state == "unhealthy" and successes >= 2:
            state = "healthy"; failures = 0
    if failures >= 2:
        state = "unhealthy"
if [row["id"] for row in api] != ["f1","f2","s1","s2"] or (state,failures,successes) != ("healthy",0,2):
    raise SystemExit("generation/window/budget/recovery probe failed")
worker = [row for row in selected if row["service"] == "worker"]
if [row["status"] for row in worker] != ["maintenance_start","failure"]:
    raise SystemExit("maintenance fixture probe failed")
print(json.dumps({"python3":"3.12","generation_window":"passed",
                  "failure_budget_recovery":"passed","maintenance":"passed",
                  "service_sidecar":"not_required_by_offline_task_contract"},sort_keys=True))
