#!/usr/bin/env python3
"""独立从冻结快照复算可行性、总价、唯一推荐、引用与副作用。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_OUTPUTS = {"comparison.csv", "recommendation.json", "report.md"}
EXPECTED_RUNTIME = {"network_events.jsonl"}
PACKAGE_KEYS = ("outbound_id", "return_id", "hotel_id", "activity_id")
COMPONENT_KEYS = ("outbound", "return", "hotel", "activity")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for category in ("transport", "hotels", "activities"):
        records = snapshot.get(category)
        if not isinstance(records, list):
            raise ValueError(f"snapshot lacks {category}")
        for record in records:
            record_id = record["record_id"]
            if record_id in result:
                raise ValueError("duplicate snapshot record")
            result[record_id] = record
    return result


def _time_between(value: str, lower: str, upper: str) -> bool:
    return lower <= value <= upper


def _valid_transport(record: dict[str, Any], direction: str, pref: dict[str, Any]) -> bool:
    trip = pref["trip"]
    hard = pref["hard_constraints"]
    if record.get("direction") != direction:
        return False
    if direction == "outbound":
        route_ok = record.get("origin") == trip["origin"] and record.get("destination") == trip["destination"]
        date_ok = record.get("travel_date") == trip["outbound_date"]
        time_ok = _time_between(record.get("departure_time", ""), hard["outbound_departure_not_before"], hard["outbound_departure_not_after"])
    else:
        route_ok = record.get("origin") == trip["destination"] and record.get("destination") == trip["origin"]
        date_ok = record.get("travel_date") == trip["return_date"]
        time_ok = record.get("arrival_time", "99:99") <= hard["return_arrival_not_after"]
    return bool(
        route_ok
        and date_ok
        and time_ok
        and float(record.get("operator_rating", 0)) >= float(hard["transport_min_operator_rating"])
        and int(record.get("checked_baggage_per_person", 0)) >= int(hard["checked_baggage_per_person_min"])
    )


def _valid_hotel(record: dict[str, Any], pref: dict[str, Any]) -> bool:
    trip = pref["trip"]
    hard = pref["hard_constraints"]
    return bool(
        record.get("available_from") <= trip["outbound_date"]
        and record.get("available_to") >= trip["return_date"]
        and float(record.get("guest_rating", 0)) >= float(hard["hotel_guest_rating_min"])
        and float(record.get("station_distance_km", 999)) <= float(hard["hotel_station_distance_km_max"])
        and record.get("breakfast_included") is hard["hotel_breakfast_included"]
        and record.get("free_cancellation") is hard["hotel_free_cancellation"]
    )


def _valid_activity(record: dict[str, Any], pref: dict[str, Any]) -> bool:
    trip = pref["trip"]
    hard = pref["hard_constraints"]
    return bool(
        record.get("activity_date") == trip["activity_date"]
        and _time_between(record.get("start_time", ""), hard["activity_start_not_before"], hard["activity_start_not_after"])
        and float(record.get("duration_hours", 0)) >= float(hard["activity_duration_hours_min"])
        and float(record.get("rating", 0)) >= float(hard["activity_rating_min"])
    )


def _cost(record: dict[str, Any], pref: dict[str, Any]) -> int:
    travelers = int(pref["trip"]["traveler_count"])
    record_id = record["record_id"]
    if record_id.startswith("TR-"):
        return int(record["adult_price_cny"]) * travelers + int(record["booking_fee_cny"])
    if record_id.startswith("HT-"):
        return int(record["nightly_price_cny"]) * int(pref["trip"]["hotel_nights"]) + int(record["stay_tax_cny"])
    if record_id.startswith("AC-"):
        return int(record["adult_price_cny"]) * travelers + int(record["booking_fee_cny"])
    raise ValueError("unsupported record")


def _quality(records: list[dict[str, Any]]) -> float:
    return round(float(records[0]["operator_rating"]) + float(records[1]["operator_rating"]) + float(records[2]["guest_rating"]) + float(records[3]["rating"]), 4)


def _package(ids: tuple[str, str, str, str], records: dict[str, dict[str, Any]], pref: dict[str, Any]) -> dict[str, Any]:
    chosen = [records[item] for item in ids]
    costs = [_cost(record, pref) for record in chosen]
    citations = [record["citation_id"] for record in chosen]
    return {
        "package_id": "+".join(ids),
        "selected": dict(zip(PACKAGE_KEYS, ids, strict=True)),
        "component_costs_cny": dict(zip(COMPONENT_KEYS, costs, strict=True)),
        "total_cny": sum(costs),
        "citations": dict(zip(COMPONENT_KEYS, citations, strict=True)),
        "quality": _quality(chosen),
        "outbound_arrival": chosen[0]["arrival_time"],
    }


def enumerate_feasible(snapshot: dict[str, Any], pref: dict[str, Any]) -> list[dict[str, Any]]:
    records = _record_map(snapshot)
    outbound = [record["record_id"] for record in snapshot["transport"] if _valid_transport(record, "outbound", pref)]
    returning = [record["record_id"] for record in snapshot["transport"] if _valid_transport(record, "return", pref)]
    hotels = [record["record_id"] for record in snapshot["hotels"] if _valid_hotel(record, pref)]
    activities = [record["record_id"] for record in snapshot["activities"] if _valid_activity(record, pref)]
    packages = []
    for ids in itertools.product(outbound, returning, hotels, activities):
        package = _package(ids, records, pref)
        if package["total_cny"] <= int(pref["budget_cny"]):
            packages.append(package)
    packages.sort(key=lambda item: (item["total_cny"], -item["quality"], item["outbound_arrival"], item["package_id"]))
    return packages


def _resolve_pointer(document: Any, pointer: str) -> Any:
    if pointer == "/":
        return document
    current = document
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _expected_report(result: dict[str, Any], records: dict[str, dict[str, Any]], pref: dict[str, Any]) -> str:
    selected = result["selected"]
    outbound = records[selected["outbound_id"]]
    returning = records[selected["return_id"]]
    hotel = records[selected["hotel_id"]]
    activity = records[selected["activity_id"]]
    citations = result["citations"]
    costs = result["component_costs_cny"]
    lines = [
        "# 海岚市双人旅行方案比较与推荐", "", "## 1. 推荐结论", "",
        f"1. 推荐组合为 `{result['package_id']}`。按固定计价规则，总费用为 **{result['total_cny']} 元**，不超过 **{result['budget_cny']} 元**预算，结余 **{result['remaining_budget_cny']} 元**。[PREF-001]",
        "2. 该组合满足全部硬约束，并且在全部可行组合中总费用最低；选择依据仅来自本地固定快照。", "", "## 2. 行程与费用", "",
        f"1. 去程 `{outbound['record_id']}`：{outbound['travel_date']} {outbound['departure_time']}—{outbound['arrival_time']}，小计 {costs['outbound']} 元。[{citations['outbound']}]",
        f"2. 返程 `{returning['record_id']}`：{returning['travel_date']} {returning['departure_time']}—{returning['arrival_time']}，小计 {costs['return']} 元。[{citations['return']}]",
        f"3. 住宿 `{hotel['record_id']}`（{hotel['name']}）：{pref['trip']['hotel_nights']} 晚，小计 {costs['hotel']} 元；住客评分 {hotel['guest_rating']}，距车站 {hotel['station_distance_km']} 千米，含早餐且可免费取消。[{citations['hotel']}]",
        f"4. 活动 `{activity['record_id']}`（{activity['name']}）：{activity['activity_date']} {activity['start_time']} 开始，时长 {activity['duration_hours']} 小时，小计 {costs['activity']} 元。[{citations['activity']}]",
        f"5. 费用复算：{costs['outbound']} + {costs['return']} + {costs['hotel']} + {costs['activity']} = **{result['total_cny']} 元**。[PREF-001]", "", "## 3. 方案比较", "",
        "1. `comparison.csv` 列出推荐方案及至少三个满足硬约束的备选方案；总价均由同一固定计价规则计算。",
        "2. 推荐只基于已冻结的交通、住宿、活动记录与用户约束，不包含实时价格、库存或快照外事实。", "",
    ]
    return "\n".join(lines)


def _expected_csv(result: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    fields = ["role", "package_id", "outbound_id", "return_id", "hotel_id", "activity_id", "outbound_cny", "return_cny", "hotel_cny", "activity_cny", "total_cny", "citations"]
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for role, package in [("recommended", result), *(("alternative", item) for item in result["alternatives"])]:
        writer.writerow({
            "role": role, "package_id": package["package_id"], **package["selected"],
            "outbound_cny": package["component_costs_cny"]["outbound"], "return_cny": package["component_costs_cny"]["return"],
            "hotel_cny": package["component_costs_cny"]["hotel"], "activity_cny": package["component_costs_cny"]["activity"],
            "total_cny": package["total_cny"], "citations": ";".join(package["citations"][key] for key in COMPONENT_KEYS),
        })
    return stream.getvalue()


def verify(case_root: Path, workspace: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    def check(check_id: str, passed: bool, evidence: str) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "evidence": evidence})
        if not passed:
            errors.append(check_id)

    case_root = case_root.resolve()
    workspace = workspace.resolve()
    try:
        expected_tree = {
            "input": "directory",
            "input/citation_index.json": "file",
            "input/preferences.json": "file",
            "input/travel_snapshot.json": "file",
            "output": "directory",
            "output/comparison.csv": "file",
            "output/recommendation.json": "file",
            "output/report.md": "file",
            "runtime": "directory",
            "runtime/network_events.jsonl": "file",
        }
        actual_tree: dict[str, str] = {}
        for path in workspace.rglob("*"):
            relative = path.relative_to(workspace).as_posix()
            if path.is_symlink():
                kind = "symlink"
            elif path.is_dir():
                kind = "directory"
            elif path.is_file():
                kind = "file"
            else:
                kind = "special"
            actual_tree[relative] = kind
        check("workspace_scope", actual_tree == expected_tree, f"actual_tree={sorted(actual_tree.items())}")

        seed_input = case_root / "fixtures" / "agent_seed" / "input"
        workspace_input = workspace / "input"
        seed_files = {path.relative_to(seed_input).as_posix(): _sha(path) for path in seed_input.rglob("*") if path.is_file()}
        actual_files = {path.relative_to(workspace_input).as_posix(): _sha(path) for path in workspace_input.rglob("*") if path.is_file() and not path.is_symlink()}
        check("input_integrity", seed_files == actual_files, f"expected_files={len(seed_files)}, actual_files={len(actual_files)}")

        runtime_files = {path.relative_to(workspace / "runtime").as_posix() for path in (workspace / "runtime").rglob("*") if path.is_file()}
        network_log = workspace / "runtime" / "network_events.jsonl"
        network_clean = network_log.is_file() and not network_log.read_text(encoding="utf-8").strip()
        check("no_network", runtime_files == EXPECTED_RUNTIME and network_clean, f"runtime_files={sorted(runtime_files)}, network_clean={network_clean}")

        output_files = {path.relative_to(workspace / "output").as_posix() for path in (workspace / "output").rglob("*") if path.is_file() and not path.is_symlink()}
        output_dirs = [path for path in (workspace / "output").rglob("*") if path.is_dir()]
        check("output_scope", output_files == EXPECTED_OUTPUTS and not output_dirs, f"output_files={sorted(output_files)}, nested_dirs={len(output_dirs)}")

        snapshot = _load_json(workspace_input / "travel_snapshot.json")
        pref = _load_json(workspace_input / "preferences.json")
        citation_index = _load_json(workspace_input / "citation_index.json")
        records = _record_map(snapshot)
        citation_map: dict[str, str] = {}
        citation_ok = True
        for entry in citation_index.get("entries", []):
            source = pref if entry["logical_path"] == "input/preferences.json" else snapshot
            target = _resolve_pointer(source, entry["json_pointer"])
            record_id = "preferences" if entry["record_id"] == "preferences" else target.get("record_id")
            target_citation = "PREF-001" if entry["record_id"] == "preferences" else target.get("citation_id")
            citation_ok = citation_ok and record_id == entry["record_id"] and target_citation == entry["citation_id"]
            citation_map[entry["citation_id"]] = entry["record_id"]
        expected_citations = {"PREF-001", *(record["citation_id"] for record in records.values())}
        check("citation_index", citation_ok and set(citation_map) == expected_citations, f"indexed={len(citation_map)}, expected={len(expected_citations)}")

        feasible = enumerate_feasible(snapshot, pref)
        if not feasible:
            raise ValueError("fixture has no feasible package")
        best = feasible[0]
        minimum_count = sum(item["total_cny"] == best["total_cny"] for item in feasible)
        check("unique_optimum", minimum_count == 1, f"feasible={len(feasible)}, minimum_count={minimum_count}, total={best['total_cny']}")

        result = _load_json(workspace / "output" / "recommendation.json")
        base_keys = {"schema_version", "package_id", "selected", "component_costs_cny", "total_cny", "citations", "budget_cny", "remaining_budget_cny", "constraint_citation", "alternatives"}
        check("result_structure", set(result) == base_keys and result.get("schema_version") == "case12_recommendation_v1", f"keys={sorted(result)}")
        selected_ids = tuple(result.get("selected", {}).get(key) for key in PACKAGE_KEYS)
        check("optimal_selection", selected_ids == tuple(best["selected"][key] for key in PACKAGE_KEYS), f"selected={selected_ids}, expected={best['package_id']}")
        cost_ok = result.get("component_costs_cny") == best["component_costs_cny"] and result.get("total_cny") == best["total_cny"] and result.get("budget_cny") == pref["budget_cny"] and result.get("remaining_budget_cny") == pref["budget_cny"] - best["total_cny"]
        check("cost_recalculation", cost_ok, f"reported_total={result.get('total_cny')}, expected_total={best['total_cny']}")
        citation_ok = result.get("citations") == best["citations"] and result.get("constraint_citation") == "PREF-001"
        check("recommendation_citations", citation_ok, f"reported={result.get('citations')}, expected={best['citations']}")

        alternatives = result.get("alternatives") if isinstance(result.get("alternatives"), list) else []
        feasible_by_id = {item["package_id"]: item for item in feasible}
        alternative_ids: list[str] = []
        alternative_ok = len(alternatives) >= 3
        for item in alternatives:
            package_id = item.get("package_id") if isinstance(item, dict) else None
            alternative_ids.append(str(package_id))
            expected = feasible_by_id.get(package_id)
            comparable = {key: item.get(key) for key in ("package_id", "selected", "component_costs_cny", "total_cny", "citations")} if isinstance(item, dict) else None
            expected_comparable = {key: expected.get(key) for key in ("package_id", "selected", "component_costs_cny", "total_cny", "citations")} if expected else None
            alternative_ok = alternative_ok and expected is not None and comparable == expected_comparable and package_id != best["package_id"]
        alternative_ok = alternative_ok and len(alternative_ids) == len(set(alternative_ids))
        check("feasible_comparison", alternative_ok, f"alternatives={alternative_ids}")

        csv_ok = (workspace / "output" / "comparison.csv").read_text(encoding="utf-8") == _expected_csv(result)
        check("comparison_consistency", csv_ok, "comparison.csv must be a canonical projection of validated JSON")
        report_text = (workspace / "output" / "report.md").read_text(encoding="utf-8")
        report_ok = report_text == _expected_report(result, records, pref)
        cited = set(re.findall(r"\[(PREF-001|CIT-[A-Z]{2}-[0-9]{3})\]", report_text))
        expected_report_citations = {"PREF-001", *best["citations"].values()}
        check("report_evidence_alignment", report_ok and cited == expected_report_citations, f"canonical={report_ok}, citations={sorted(cited)}")
    except Exception as exc:
        check("verifier_runtime", False, f"{type(exc).__name__}: {exc}")
        feasible = []
        best = {"total_cny": 0}
        minimum_count = 0

    accepted = bool(checks) and all(item["passed"] for item in checks)
    return {
        "schema_version": "case12_verifier_result_v1",
        "accepted": accepted,
        "score": round(sum(item["passed"] for item in checks) / len(checks), 6) if checks else 0,
        "checks": checks,
        "errors": errors,
        "evidence": {
            "feasible_package_count": len(feasible),
            "unique_minimum": minimum_count == 1,
            "expected_total_cny": int(best["total_cny"]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.case_root, args.workspace)
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
