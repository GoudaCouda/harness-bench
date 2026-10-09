#!/usr/bin/env python3
"""Verify the shared agent runtime for 228-event-time-watermark-late-drop."""

import datetime
import json
import sys


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")
    event = datetime.datetime.fromisoformat('2026-01-01T00:00:00+00:00')
    assert event + datetime.timedelta(minutes=5) > event
    print(json.dumps({"environment": "passed", "task_id": "228-event-time-watermark-late-drop"}, sort_keys=True))


if __name__ == "__main__":
    main()
