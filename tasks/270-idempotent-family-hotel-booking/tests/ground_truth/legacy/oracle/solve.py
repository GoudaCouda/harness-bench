#!/usr/bin/env python3
"""Reference execution for case_16; never mounted into the Agent boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
TOOL = CASE_ROOT / "environment" / "hotel_tools.py"


def call_tool(work_root: Path, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--work-root", str(work_root), "--tool", tool],
        input=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"tool failed with exit code {completed.returncode}")
    result = json.loads(completed.stdout)
    if result.get("status") != "ok":
        raise RuntimeError("tool returned a non-success result")
    return result


def solve(work_root: Path) -> dict[str, Any]:
    search_request = {
        "city": "澄江市",
        "district": "中心区",
        "check_in": "2026-11-18",
        "check_out": "2026-11-21",
        "adults": 2,
        "children": 1,
        "room_type": "family_standard",
        "breakfast_required": True,
        "non_smoking_required": True,
        "max_nightly_rate_cny": 620,
    }
    search = call_tool(work_root, "search_hotel_inventory", search_request)
    if search["candidate_count"] != 1:
        raise RuntimeError("oracle search did not return exactly one candidate")
    selected = search["candidates"][0]
    if selected["hotel_id"] != "H-CJ-002":
        raise RuntimeError("oracle selected an unexpected hotel")
    create_request = {
        "request_id": "REQ-NW16-001",
        "user_id": "CUS-042",
        "hotel_id": selected["hotel_id"],
        "check_in": "2026-11-18",
        "check_out": "2026-11-21",
        "adults": 2,
        "children": 1,
        "room_type": "family_standard",
    }
    created = call_tool(work_root, "create_hotel_booking", create_request)
    booking_id = created["booking"]["booking_id"]
    queried = call_tool(
        work_root, "get_hotel_booking", {"booking_id": booking_id}
    )
    if queried["booking"] != created["booking"]:
        raise RuntimeError("create and query results disagree")
    return {
        "status": "completed",
        "selected_hotel_id": selected["hotel_id"],
        "booking": queried["booking"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = solve(args.work_root)
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "error": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
