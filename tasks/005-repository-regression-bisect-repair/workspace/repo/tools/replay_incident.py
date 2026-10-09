#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ledger_router.eligibility import collection_decision  # noqa: E402


def main() -> int:
    rows = json.loads((ROOT / "fixtures/incident_replay.json").read_text())
    failures = []
    for row in rows:
        actual = list(collection_decision(row["invoice"]))
        if actual != row["expected"]:
            failures.append(
                {"id": row["id"], "expected": row["expected"], "actual": actual}
            )
    if failures:
        print(json.dumps({"status": "fail", "failures": failures}, indent=2))
        return 1
    print(json.dumps({"status": "pass", "cases": [row["id"] for row in rows]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
