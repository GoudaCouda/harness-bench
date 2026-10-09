"""Compute a synthetic cohort mean from a controlled survey export."""

from __future__ import annotations

import csv
import statistics
import sys


with open(sys.argv[1], encoding="utf-8", newline="") as handle:
    scores = [int(row["memory_score"]) for row in csv.DictReader(handle)]
print(f"mean_memory_score={statistics.fmean(scores):.2f}")
