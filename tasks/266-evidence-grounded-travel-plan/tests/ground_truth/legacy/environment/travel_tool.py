#!/usr/bin/env python3
"""Agent 可见的本地快照读取与结构化交付工具；不判断最优答案。"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Any


CATEGORIES = ("transport", "hotels", "activities")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path.name}")
    return value


def _workspace(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise ValueError("workspace is missing or unsafe")
    for name in ("input", "output", "runtime"):
        child = resolved / name
        if not child.is_dir() or child.is_symlink():
            raise ValueError(f"workspace lacks safe {name} directory")
    return resolved


def _records(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for category in CATEGORIES:
        for record in snapshot.get(category, []):
            result[record["record_id"]] = record
    return result


def _component_cost(record: dict[str, Any], preferences: dict[str, Any]) -> int:
    travelers = int(preferences["trip"]["traveler_count"])
    if record["record_id"].startswith("TR-"):
        return int(record["adult_price_cny"]) * travelers + int(record["booking_fee_cny"])
    if record["record_id"].startswith("HT-"):
        return int(record["nightly_price_cny"]) * int(preferences["trip"]["hotel_nights"]) + int(record["stay_tax_cny"])
    if record["record_id"].startswith("AC-"):
        return int(record["adult_price_cny"]) * travelers + int(record["booking_fee_cny"])
    raise ValueError("unsupported record type")


def _selection(ids: list[str], records: dict[str, dict[str, Any]], preferences: dict[str, Any]) -> dict[str, Any]:
    keys = ("outbound_id", "return_id", "hotel_id", "activity_id")
    if len(ids) != len(keys) or len(set(ids)) != len(ids):
        raise ValueError("a package needs four distinct component IDs")
    chosen = [records[item] for item in ids]
    if chosen[0].get("direction") != "outbound" or chosen[1].get("direction") != "return":
        raise ValueError("transport directions do not match package positions")
    if not ids[2].startswith("HT-") or not ids[3].startswith("AC-"):
        raise ValueError("hotel or activity position is invalid")
    costs = [_component_cost(record, preferences) for record in chosen]
    citations = [record["citation_id"] for record in chosen]
    return {
        "package_id": "+".join(ids),
        "selected": dict(zip(keys, ids, strict=True)),
        "component_costs_cny": dict(zip(("outbound", "return", "hotel", "activity"), costs, strict=True)),
        "total_cny": sum(costs),
        "citations": dict(zip(("outbound", "return", "hotel", "activity"), citations, strict=True)),
    }


def _render_report(result: dict[str, Any], records: dict[str, dict[str, Any]], preferences: dict[str, Any]) -> str:
    selected = result["selected"]
    outbound = records[selected["outbound_id"]]
    returning = records[selected["return_id"]]
    hotel = records[selected["hotel_id"]]
    activity = records[selected["activity_id"]]
    citations = result["citations"]
    costs = result["component_costs_cny"]
    lines = [
        "# 海岚市双人旅行方案比较与推荐",
        "",
        "## 1. 推荐结论",
        "",
        f"1. 推荐组合为 `{result['package_id']}`。按固定计价规则，总费用为 **{result['total_cny']} 元**，不超过 **{result['budget_cny']} 元**预算，结余 **{result['remaining_budget_cny']} 元**。[PREF-001]",
        "2. 该组合满足全部硬约束，并且在全部可行组合中总费用最低；选择依据仅来自本地固定快照。",
        "",
        "## 2. 行程与费用",
        "",
        f"1. 去程 `{outbound['record_id']}`：{outbound['travel_date']} {outbound['departure_time']}—{outbound['arrival_time']}，小计 {costs['outbound']} 元。[{citations['outbound']}]",
        f"2. 返程 `{returning['record_id']}`：{returning['travel_date']} {returning['departure_time']}—{returning['arrival_time']}，小计 {costs['return']} 元。[{citations['return']}]",
        f"3. 住宿 `{hotel['record_id']}`（{hotel['name']}）：{preferences['trip']['hotel_nights']} 晚，小计 {costs['hotel']} 元；住客评分 {hotel['guest_rating']}，距车站 {hotel['station_distance_km']} 千米，含早餐且可免费取消。[{citations['hotel']}]",
        f"4. 活动 `{activity['record_id']}`（{activity['name']}）：{activity['activity_date']} {activity['start_time']} 开始，时长 {activity['duration_hours']} 小时，小计 {costs['activity']} 元。[{citations['activity']}]",
        f"5. 费用复算：{costs['outbound']} + {costs['return']} + {costs['hotel']} + {costs['activity']} = **{result['total_cny']} 元**。[PREF-001]",
        "",
        "## 3. 方案比较",
        "",
        "1. `comparison.csv` 列出推荐方案及至少三个满足硬约束的备选方案；总价均由同一固定计价规则计算。",
        "2. 推荐只基于已冻结的交通、住宿、活动记录与用户约束，不包含实时价格、库存或快照外事实。",
        "",
    ]
    return "\n".join(lines)


def _render_csv(result: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    fields = ["role", "package_id", "outbound_id", "return_id", "hotel_id", "activity_id", "outbound_cny", "return_cny", "hotel_cny", "activity_cny", "total_cny", "citations"]
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for role, package in [("recommended", result), *(("alternative", item) for item in result["alternatives"])]:
        writer.writerow({
            "role": role,
            "package_id": package["package_id"],
            **package["selected"],
            "outbound_cny": package["component_costs_cny"]["outbound"],
            "return_cny": package["component_costs_cny"]["return"],
            "hotel_cny": package["component_costs_cny"]["hotel"],
            "activity_cny": package["component_costs_cny"]["activity"],
            "total_cny": package["total_cny"],
            "citations": ";".join(package["citations"][key] for key in ("outbound", "return", "hotel", "activity")),
        })
    return stream.getvalue()


def submit(workspace: Path, selected_ids: list[str], alternatives: list[list[str]]) -> dict[str, Any]:
    workspace = _workspace(workspace)
    snapshot = _load_json(workspace / "input" / "travel_snapshot.json")
    preferences = _load_json(workspace / "input" / "preferences.json")
    records = _records(snapshot)
    chosen = _selection(selected_ids, records, preferences)
    alternative_rows = [_selection(ids, records, preferences) for ids in alternatives]
    if len(alternative_rows) < 3:
        raise ValueError("at least three comparison alternatives are required")
    chosen.update({
        "schema_version": "case12_recommendation_v1",
        "budget_cny": int(preferences["budget_cny"]),
        "remaining_budget_cny": int(preferences["budget_cny"]) - chosen["total_cny"],
        "constraint_citation": "PREF-001",
        "alternatives": alternative_rows,
    })
    output = workspace / "output"
    output.mkdir(exist_ok=True)
    (output / "recommendation.json").write_text(json.dumps(chosen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "comparison.csv").write_text(_render_csv(chosen), encoding="utf-8")
    (output / "report.md").write_text(_render_report(chosen, records, preferences), encoding="utf-8")
    return chosen


def _parse_package(value: str) -> list[str]:
    values = [item.strip() for item in value.split(",")]
    if len(values) != 4 or any(not item for item in values):
        raise argparse.ArgumentTypeError("package must contain four comma-separated IDs")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("category", choices=CATEGORIES)
    get_cmd = sub.add_parser("get")
    get_cmd.add_argument("record_id")
    submit_cmd = sub.add_parser("submit")
    submit_cmd.add_argument("--selected", type=_parse_package, required=True)
    submit_cmd.add_argument("--alternative", type=_parse_package, action="append", required=True)
    args = parser.parse_args()
    workspace = _workspace(args.workspace)
    snapshot = _load_json(workspace / "input" / "travel_snapshot.json")
    records = _records(snapshot)
    if args.command == "list":
        print(json.dumps(snapshot[args.category], ensure_ascii=False, indent=2, sort_keys=True))
    elif args.command == "get":
        if args.record_id not in records:
            raise ValueError("unknown record ID")
        print(json.dumps(records[args.record_id], ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(submit(workspace, args.selected, args.alternative), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
