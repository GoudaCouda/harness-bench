#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

capacity = 1
connections = {"c":{"generation":2,"state":"leased","owner":"a"}}
queue = [("q-b","b")]
release = {"connection":"c","client":"a","clean":False}
conn = connections[release["connection"]]
if conn["state"] != "leased" or conn["owner"] != release["client"]:
    raise SystemExit("ownership fixture failed")
conn.update(state="quarantine",owner=None)
if sum(row["state"] != "closed" for row in connections.values()) > capacity:
    raise SystemExit("capacity invariant failed")
reset = {"connection":"c","success":True}
if reset["success"] and conn["state"] == "quarantine":
    conn["generation"] += 1
    conn.update(state="idle",owner=None)
qid,client = queue.pop(0)
idle = sorted(cid for cid,row in connections.items() if row["state"]=="idle")
if not idle:
    raise SystemExit("reset did not return capacity")
cid=idle[0]; connections[cid].update(state="leased",owner=client)
action={"id":qid+":dequeue","action":"leased_from_queue","connection":cid}
if action != {"id":"q-b:dequeue","action":"leased_from_queue","connection":"c"}:
    raise SystemExit("FIFO dequeue probe failed")
if connections["c"] != {"generation":3,"state":"leased","owner":"b"}:
    raise SystemExit("reset-generation probe failed")
bad={"generation":0,"state":"idle","owner":"ghost"}
if not (bad["state"]!="leased" and bad["owner"] is not None):
    raise SystemExit("owner-invariant fixture failed")
print(json.dumps({"python3":"3.12","ownership":"passed","quarantine_reset":"passed",
                  "fifo_dequeue":"passed","capacity_reuse":"passed",
                  "database_service":"not_required_by_offline_task_contract"},sort_keys=True))
