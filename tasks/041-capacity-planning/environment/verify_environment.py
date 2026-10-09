#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

required_capacity = 2391.2 * (1 + 0.30)
catalog = [("c7g.large", 610, 0.081), ("c7g.xlarge", 1220, 0.152)]
plans = []
for instance_type, capacity, hourly_cost in catalog:
    count = math.ceil(required_capacity / capacity)
    provided = count * capacity
    if provided >= required_capacity:
        plans.append((round(count * hourly_cost, 3), count, instance_type, provided))

selected = min(plans)
if selected != (0.456, 3, "c7g.xlarge", 3660):
    raise SystemExit(f"capacity enumeration probe failed: {selected!r}")
zones = {"zone-a": selected[1] // 2 + selected[1] % 2, "zone-b": selected[1] // 2}
if sum(zones.values()) != selected[1] or max(zones.values()) - min(zones.values()) > 1:
    raise SystemExit("zone distribution probe failed")

print(json.dumps({"python3": "3.12", "enumeration": "passed", "zone_spread": "passed"}, sort_keys=True))
