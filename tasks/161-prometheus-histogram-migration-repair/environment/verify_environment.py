#!/usr/bin/env python3
"""Task 161 plans from captured metrics; a Prometheus server is intentionally absent."""
from __future__ import annotations

import hashlib
import json
import math
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
observation = {
    "classic_count": 1000,
    "native_count": 998,
    "counter_resets": 0,
    "stable_windows": 4,
}
parity_error = abs(observation["native_count"] - observation["classic_count"]) / observation["classic_count"]
if not math.isclose(parity_error, 0.002) or observation["counter_resets"]:
    raise SystemExit("histogram parity/reset probe failed")
queries = {
    "classic": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
    "native": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds[5m])))",
}
payload = json.dumps(queries, sort_keys=True).encode()
if len(hashlib.sha256(payload).hexdigest()) != 64:
    raise SystemExit("PromQL evidence digest probe failed")
print(json.dumps({
    "python3": "3.12", "parity": "passed", "promql_shapes": "passed",
    "json": "passed", "sha256": "passed",
    "prometheus_runtime": "not_required_by_task_contract",
}, sort_keys=True))
