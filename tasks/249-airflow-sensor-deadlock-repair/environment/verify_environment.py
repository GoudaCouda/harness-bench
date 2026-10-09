#!/usr/bin/env python3
"""Verify the shared agent runtime for 249-airflow-sensor-deadlock-repair."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    purchased = datetime.date(2025, 1, 1)
    requested = datetime.date(2026, 1, 1)
    assert (requested - purchased).days == 365
    print(json.dumps({"environment": "passed", "task_id": '249-airflow-sensor-deadlock-repair'}, sort_keys=True))


if __name__ == "__main__":
    main()
