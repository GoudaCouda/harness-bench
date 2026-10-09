#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    inputs = workspace / "inputs"
    rules = load_json(inputs / "sla_rules.json")
    contract_id = str(rules["contract_id"])
    quarter = str(rules["quarter"])
    region_id = str(rules["target_region_id"])

    with (inputs / "region_registry.csv").open(encoding="utf-8", newline="") as stream:
        regions = list(csv.DictReader(stream))
    if not any(
        row["region_id"] == region_id
        and row["contract_id"] == contract_id
        and row["service_tier"] == "mission_critical"
        and row["active"] == "true"
        for row in regions
    ):
        raise ValueError("target region registry mismatch")

    records = [
        json.loads(line)
        for line in (inputs / "service_events_2025_q3.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    eligibility = rules["eligibility"]
    grace = int(eligibility["per_event_grace_minutes"])
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for record in records:
        event_id = str(record["event_id"])
        if record.get("region_id") != region_id:
            excluded.append({"event_id": event_id, "reason_code": "out_of_scope_region"})
        elif record.get("validated") is not True:
            excluded.append({"event_id": event_id, "reason_code": "unvalidated_record"})
        elif record.get("event_type") != eligibility["included_event_type"]:
            excluded.append({"event_id": event_id, "reason_code": "scheduled_maintenance"})
        else:
            duration = int(record["duration_minutes"])
            eligible.append(
                {
                    "event_id": event_id,
                    "severity": str(record["severity"]),
                    "duration_minutes": duration,
                    "grace_minutes": grace,
                    "eligible_minutes": max(0, duration - grace),
                }
            )
    eligible.sort(key=lambda item: item["event_id"])
    excluded.sort(key=lambda item: item["event_id"])
    eligible_ids = [item["event_id"] for item in eligible]
    eligible_total = sum(int(item["eligible_minutes"]) for item in eligible)
    p1_ids = [item["event_id"] for item in eligible if item["severity"] == "P1"]

    credit_rule = rules["credit"]
    rate = int(credit_rule["rate_cny_per_eligible_minute"])
    base_credit = eligible_total * rate
    repeat_triggered = len(eligible) >= int(credit_rule["repeat_incident_threshold"])
    numerator = int(credit_rule["multiplier_numerator"]) if repeat_triggered else 1
    denominator = int(credit_rule["multiplier_denominator"]) if repeat_triggered else 1
    if (base_credit * numerator) % denominator:
        raise ValueError("credit multiplier must produce an exact integer")
    final_credit = base_credit * numerator // denominator

    remediation_rule = rules["remediation"]
    remediation_triggered = (
        len(p1_ids) >= int(remediation_rule["minimum_p1_events"])
        and eligible_total >= int(remediation_rule["minimum_total_eligible_minutes"])
    )
    remediation_level = (
        remediation_rule["triggered_level"]
        if remediation_triggered
        else remediation_rule["default_level"]
    )
    remediation_days = int(
        remediation_rule["triggered_due_business_days"]
        if remediation_triggered
        else remediation_rule["default_due_business_days"]
    )
    triggered_credit_rules = [credit_rule["base_rule_id"]]
    if repeat_triggered:
        triggered_credit_rules.append(credit_rule["repeat_rule_id"])

    result = {
        "schema_version": "case14_sla_credit_assessment_v2",
        "contract_id": contract_id,
        "quarter": quarter,
        "region_id": region_id,
        "event_assessment": {
            "eligible_event_ids": eligible_ids,
            "eligible_minutes_by_event": eligible,
            "eligible_minutes_total": eligible_total,
            "p1_event_count": len(p1_ids),
        },
        "credit": {
            "rate_cny_per_minute": rate,
            "base_credit_cny": base_credit,
            "repeat_incident_threshold": int(credit_rule["repeat_incident_threshold"]),
            "eligible_event_count": len(eligible),
            "multiplier_numerator": numerator,
            "multiplier_denominator": denominator,
            "final_credit_cny": final_credit,
            "triggered_rule_ids": sorted(str(value) for value in triggered_credit_rules),
            "evidence_ids": sorted(eligible_ids),
        },
        "remediation": {
            "level": str(remediation_level),
            "due_business_days": remediation_days,
            "triggered_rule_id": str(remediation_rule["rule_id"]),
            "evidence_ids": sorted([*p1_ids, str(remediation_rule["rule_id"])]),
        },
        "excluded_records": excluded,
        "ignored_sources": sorted(
            list(rules["ignored_sources"]), key=lambda item: item["source_id"]
        ),
    }
    output = workspace / "outputs" / "sla_credit_assessment.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
