#!/usr/bin/env python3
"""隐藏参考求解器：独立枚举可行组合后调用 Agent 可见交付工具。"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
from pathlib import Path
from typing import Any


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("case12_travel_tool", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load travel tool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("fixture must be an object")
    return value


def _between(value: str, lower: str, upper: str) -> bool:
    return lower <= value <= upper


def _valid(record: dict[str, Any], role: str, pref: dict[str, Any]) -> bool:
    trip = pref["trip"]
    hard = pref["hard_constraints"]
    if role == "outbound":
        return bool(record["direction"] == "outbound" and record["origin"] == trip["origin"] and record["destination"] == trip["destination"] and record["travel_date"] == trip["outbound_date"] and _between(record["departure_time"], hard["outbound_departure_not_before"], hard["outbound_departure_not_after"]) and record["operator_rating"] >= hard["transport_min_operator_rating"] and record["checked_baggage_per_person"] >= hard["checked_baggage_per_person_min"])
    if role == "return":
        return bool(record["direction"] == "return" and record["origin"] == trip["destination"] and record["destination"] == trip["origin"] and record["travel_date"] == trip["return_date"] and record["arrival_time"] <= hard["return_arrival_not_after"] and record["operator_rating"] >= hard["transport_min_operator_rating"] and record["checked_baggage_per_person"] >= hard["checked_baggage_per_person_min"])
    if role == "hotel":
        return bool(record["available_from"] <= trip["outbound_date"] and record["available_to"] >= trip["return_date"] and record["guest_rating"] >= hard["hotel_guest_rating_min"] and record["station_distance_km"] <= hard["hotel_station_distance_km_max"] and record["breakfast_included"] is True and record["free_cancellation"] is True)
    return bool(record["activity_date"] == trip["activity_date"] and _between(record["start_time"], hard["activity_start_not_before"], hard["activity_start_not_after"]) and record["duration_hours"] >= hard["activity_duration_hours_min"] and record["rating"] >= hard["activity_rating_min"])


def solve(case_root: Path, workspace: Path) -> dict[str, Any]:
    pref = _load(workspace / "input" / "preferences.json")
    snapshot = _load(workspace / "input" / "travel_snapshot.json")
    tool = _load_module(case_root / "environment" / "travel_tool.py")
    records = tool._records(snapshot)
    pools = [
        [item["record_id"] for item in snapshot["transport"] if _valid(item, "outbound", pref)],
        [item["record_id"] for item in snapshot["transport"] if _valid(item, "return", pref)],
        [item["record_id"] for item in snapshot["hotels"] if _valid(item, "hotel", pref)],
        [item["record_id"] for item in snapshot["activities"] if _valid(item, "activity", pref)],
    ]
    feasible: list[tuple[int, float, str, list[str]]] = []
    for ids_tuple in itertools.product(*pools):
        ids = list(ids_tuple)
        package = tool._selection(ids, records, pref)
        if package["total_cny"] > pref["budget_cny"]:
            continue
        selected_records = [records[item] for item in ids]
        quality = selected_records[0]["operator_rating"] + selected_records[1]["operator_rating"] + selected_records[2]["guest_rating"] + selected_records[3]["rating"]
        feasible.append((package["total_cny"], -quality, selected_records[0]["arrival_time"], ids))
    feasible.sort(key=lambda item: (item[0], item[1], item[2], "+".join(item[3])))
    if len(feasible) < 4:
        raise ValueError("fixture needs at least four feasible packages")
    selected = feasible[0][3]
    alternatives = [row[3] for row in feasible[1:4]]
    return tool.submit(workspace, selected, alternatives)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(solve(args.case_root.resolve(), args.workspace.resolve()), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
