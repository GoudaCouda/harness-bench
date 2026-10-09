#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

import yaml
from harnessbench.grading.pure_function import audit_pure_function, run_pure_function
from harnessbench.grading.task_checks import observation, sources_unchanged, workspace_redline_violations

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """
def reconcile_object_events(objects, events, policy):
    current = dict(objects)
    for event in events:
        key = event['key']
        old = current.get(key)
        if old is None or int(event['sequencer'], 16) > int(old['sequencer'], 16):
            current[key] = {'sequencer': event['sequencer']}
    return {'objects': current}
"""
cases = [{
    "objects": {"a": {"sequencer": "0f"}},
    "events": [{"key": "a", "sequencer": "10"}],
    "policy": {},
}]
safe, detail = audit_pure_function(source, "reconcile_object_events")
if not safe:
    raise SystemExit(f"grader pure audit probe failed: {detail}")
actual, detail = run_pure_function(
    source, "reconcile_object_events", cases, ("objects", "events", "policy")
)
if not actual or actual[0].get("value") != {"objects": {"a": {"sequencer": "10"}}}:
    raise SystemExit(f"grader pure worker probe failed: {detail}")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(callable(value) for value in (observation, sources_unchanged, workspace_redline_violations)):
    raise SystemExit("grader event API import probe failed")
print(json.dumps({"python3": "3.10", "pure_worker": "passed", "yaml": "passed"}, sort_keys=True))
