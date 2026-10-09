#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import statistics
import sys
import xml.etree.ElementTree as ET


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

events = list(
    csv.DictReader(
        io.StringIO("study,a,n1,c,n0\nA,8,100,12,100\nB,5,80,9,80\n")
    )
)
effects = [
    math.log(
        (float(row["a"]) / float(row["n1"]))
        / (float(row["c"]) / float(row["n0"]))
    )
    for row in events
]
if not math.isfinite(statistics.fmean(effects)):
    raise SystemExit("meta-analysis arithmetic probe failed")
root = ET.fromstring(
    '<svg xmlns="http://www.w3.org/2000/svg"><text>POOLED</text></svg>'
)
if not root.tag.endswith("svg"):
    raise SystemExit("SVG generation/parsing probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "csv": "passed",
            "math": "passed",
            "statistics": "passed",
            "svg": "passed",
        },
        sort_keys=True,
    )
)
