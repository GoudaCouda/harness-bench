#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/cold_chain.db"
PLAN_FIELDS = {
    "schema_version",
    "recovery_id",
    "source_checkpoint",
    "decisions",
    "external_actions_executed",
}
DECISION_FIELDS = {
    "lot_id",
    "container_id",
    "primary_device_id",
    "gap_intervals_utc",
    "fallback_device_id",
    "fallback_calibration_id",
    "observed_min_c",
    "observed_max_c",
    "out_of_range_minutes",
    "disposition",
    "local_mutations",
    "evidence_refs",
    "next_local_action",
}
SET_FIELDS = ("gap_intervals_utc", "local_mutations", "evidence_refs")
TABLES = (
    "lots",
    "containers",
    "devices",
    "device_assignments",
    "calibrations",
    "excursion_assessments",
    "holds",
    "recovery_runs",
    "recovery_journal",
    "system_state",
)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in TABLES:
        raise ValueError(f"unsupported table: {table}")
    return [
        dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")
    ]


def utc(local: str, offset: str) -> str:
    value = datetime.fromisoformat(local + offset).astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_readings() -> tuple[list[dict[str, Any]], bool]:
    result: list[dict[str, Any]] = []
    for line in (
        (ROOT / "evidence/logger_readings.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        row = json.loads(line)
        row["observed_at_utc"] = utc(row["observed_local"], row["utc_offset"])
        result.append(row)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in result:
        groups.setdefault((row["device_id"], int(row["sequence"])), []).append(row)
    clean = []
    duplicate_ok = True
    for key in sorted(groups):
        group = groups[key]
        payloads = {
            (row["observed_local"], row["utc_offset"], float(row["temperature_c"]))
            for row in group
        }
        if len(payloads) != 1:
            duplicate_ok = False
            continue
        clean.append(group[0])
    return clean, duplicate_ok


def protected_hashes_ok() -> tuple[bool, dict[str, str]]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files", {})
    actual = {name: digest((ROOT / name).read_bytes()) for name in files}
    return actual == files, actual


def baseline_lots(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    current = {row["lot_id"]: row for row in rows(connection, "lots")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs")}
    for journal in rows(connection, "recovery_journal"):
        run = runs.get(journal["recovery_id"])
        is_current_recovery = (
            journal["recovery_id"]
            == load_json(ROOT / "policy/cold_chain_policy.json")["recovery_id"]
        )
        if run and (
            (run["status"] == "interrupted" and not journal["restored"])
            or is_current_recovery
        ):
            current[journal["lot_id"]] = json.loads(journal["before_json"])
    return [current[key] for key in sorted(current)]


def source_checkpoint(connection: sqlite3.Connection) -> str:
    recovery_id = load_json(ROOT / "policy/cold_chain_policy.json")["recovery_id"]
    committed = current_run(connection, recovery_id)
    if committed is not None:
        return str(committed["source_checkpoint"])
    manifest = load_json(ROOT / "policy/source_manifest.json")["files"]
    revision = connection.execute(
        "SELECT value FROM system_state WHERE key='inventory_revision'"
    ).fetchone()[0]
    value = {
        "immutable_source_hashes": manifest,
        "baseline_lots": baseline_lots(connection),
        "containers": rows(connection, "containers"),
        "devices": rows(connection, "devices"),
        "device_assignments": rows(connection, "device_assignments"),
        "calibrations": rows(connection, "calibrations"),
        "inventory_revision": int(revision),
    }
    return digest(canonical(value))


def signed_ranges(readings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    trust = load_json(ROOT / "evidence/logger_trust.json")
    raw = load_json(ROOT / "evidence/secondary_ranges.json")
    answer = {}
    source_rows = []
    for line in (
        (ROOT / "evidence/logger_readings.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        source_rows.append(json.loads(line))
    for record in raw.get("ranges", []):
        payload = {
            key: value
            for key, value in record.items()
            if key not in {"key_id", "signature"}
        }
        selected = [
            row
            for row in source_rows
            if row.get("device_id") == record.get("device_id")
            and int(record.get("sequence_start", -1))
            <= int(row.get("sequence", -2))
            <= int(record.get("sequence_end", -1))
        ]
        valid = (
            record.get("key_id") == trust.get("key_id")
            and record.get("signature")
            == digest(
                canonical(payload)
                + str(trust.get("verification_material", "")).encode()
            )
            and record.get("readings_sha256") == digest(canonical(selected))
        )
        answer[str(record.get("range_id"))] = {**record, "valid": valid}
    return answer


def expected_times(start: str, end: str, minutes: int) -> list[str]:
    current, finish = dt(start), dt(end)
    answer = []
    while current <= finish:
        answer.append(current.strftime("%Y-%m-%dT%H:%M:%SZ"))
        current += timedelta(minutes=minutes)
    return answer


def gap_ranges(times: list[str], interval: int) -> list[str]:
    if not times:
        return []
    values = sorted(dt(item) for item in times)
    groups = [[values[0]]]
    for value in values[1:]:
        if value - groups[-1][-1] == timedelta(minutes=interval):
            groups[-1].append(value)
        else:
            groups.append([value])
    return [
        f"{group[0].strftime('%Y-%m-%dT%H:%M:%SZ')}/{group[-1].strftime('%Y-%m-%dT%H:%M:%SZ')}"
        for group in groups
    ]


def assignment_for(
    assignments: list[dict[str, Any]], container: str, role: str, start: str, end: str
) -> dict[str, Any] | None:
    matches = [
        row
        for row in assignments
        if row["container_id"] == container
        and row["role"] == role
        and dt(row["valid_from_utc"]) <= dt(start)
        and dt(row["valid_to_utc"]) >= dt(end)
    ]
    return matches[0] if len(matches) == 1 else None


def calibration_for(
    calibrations: list[dict[str, Any]], device: str, start: str, end: str
) -> dict[str, Any] | None:
    matches = [
        row
        for row in calibrations
        if row["device_id"] == device
        and row["status"] == "valid"
        and dt(row["valid_from_utc"]) <= dt(start)
        and dt(row["valid_to_utc"]) >= dt(end)
    ]
    return matches[0] if len(matches) == 1 else None


def recovery_inputs(connection: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Load verified cold-chain evidence without constructing a plan."""
    owned = connection is None
    connection = connection or connect()
    try:
        policy = load_json(ROOT / "policy/cold_chain_policy.json")
        readings, duplicate_ok = load_readings()
        ranges = signed_ranges(readings)
        assignments = rows(connection, "device_assignments")
        calibrations = rows(connection, "calibrations")
        containers = {
            row["container_id"]: row for row in rows(connection, "containers")
        }
        baseline = baseline_lots(connection)
        hashes_ok, _ = protected_hashes_ok()
        return {
            "policy": policy,
            "readings": readings,
            "signed_ranges": ranges,
            "assignments": assignments,
            "calibrations": calibrations,
            "containers": containers,
            "duplicate_ok": duplicate_ok,
            "sources_ok": hashes_ok,
            "baseline_lots": baseline,
            "source_checkpoint": source_checkpoint(connection),
        }
    finally:
        if owned:
            connection.close()


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    value = dict(plan)
    normalized = []
    for raw in (
        value.get("decisions", []) if isinstance(value.get("decisions"), list) else []
    ):
        row = dict(raw) if isinstance(raw, dict) else {}
        for field in SET_FIELDS:
            if isinstance(row.get(field), list):
                row[field] = sorted(row[field])
        normalized.append(row)
    value["decisions"] = sorted(normalized, key=lambda row: str(row.get("lot_id")))
    return value


def semantic_digest(plan: dict[str, Any]) -> str:
    return digest(canonical(normalize_plan(plan)))


def load_plan(name: str) -> dict[str, Any]:
    path = (ROOT / name).resolve()
    if path.parent != ROOT or not path.is_file():
        raise ValueError("plan must be a regular JSON file in the workspace root")
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError("plan must be an object")
    return value


def validate(
    plan: dict[str, Any], facts: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    plan = normalize_plan(plan)
    actual_rows = (
        plan.get("decisions") if isinstance(plan.get("decisions"), list) else []
    )
    actual_map = {
        row.get("lot_id"): row for row in actual_rows if isinstance(row, dict)
    }
    lot_ids = {row["lot_id"] for row in facts["baseline_lots"]}
    checks: dict[str, Any] = {
        "schema": set(plan) == PLAN_FIELDS
        and plan.get("schema_version") == 1
        and all(
            isinstance(row, dict) and set(row) == DECISION_FIELDS for row in actual_rows
        ),
        "recovery_identity": plan.get("recovery_id") == facts["policy"]["recovery_id"],
        "source_checkpoint": plan.get("source_checkpoint")
        == facts["source_checkpoint"],
        "source_integrity": facts["sources_ok"],
        "duplicate_readings_consistent": facts["duplicate_ok"],
        "lot_coverage": len(actual_rows) == len(lot_ids)
        and set(actual_map) == lot_ids,
        "offline_boundary": plan.get("external_actions_executed") is False,
    }
    mismatches: dict[str, list[str]] = {}
    policy = facts["policy"]
    interval = int(policy["sample_interval_minutes"])
    lower = float(policy["temperature_band_c"]["lower_inclusive"])
    upper = float(policy["temperature_band_c"]["upper_inclusive"])
    for lot in facts["baseline_lots"]:
        lot_id = str(lot["lot_id"])
        container = facts["containers"][lot["container_id"]]
        start, end = container["evaluation_start_utc"], container["evaluation_end_utc"]
        times = expected_times(start, end, interval)
        primary = assignment_for(
            facts["assignments"], lot["container_id"], "primary", start, end
        )
        primary_id = primary["device_id"] if primary else None
        primary_rows = {
            row["observed_at_utc"]: row
            for row in facts["readings"]
            if row["device_id"] == primary_id and start <= row["observed_at_utc"] <= end
        }
        missing = [stamp for stamp in times if stamp not in primary_rows]
        gaps = gap_ranges(missing, interval)
        effective = dict(primary_rows)
        fallback = calibration = range_record = None
        if missing:
            gap_start, gap_end = missing[0], missing[-1]
            secondary = assignment_for(
                facts["assignments"], lot["container_id"], "secondary", gap_start, gap_end
            )
            if secondary:
                candidate_cal = calibration_for(
                    facts["calibrations"], secondary["device_id"], gap_start, gap_end
                )
                candidates = [
                    row for row in facts["signed_ranges"].values()
                    if row["device_id"] == secondary["device_id"]
                    and row["container_id"] == lot["container_id"]
                    and row["valid"]
                    and dt(row["coverage_start_utc"]) <= dt(gap_start)
                    and dt(row["coverage_end_utc"]) >= dt(gap_end)
                ]
                secondary_rows = {
                    row["observed_at_utc"]: row
                    for row in facts["readings"]
                    if row["device_id"] == secondary["device_id"]
                }
                if candidate_cal and len(candidates) == 1 and all(
                    stamp in secondary_rows for stamp in missing
                ):
                    fallback, calibration, range_record = secondary, candidate_cal, candidates[0]
                    for stamp in missing:
                        adjusted = dict(secondary_rows[stamp])
                        adjusted["temperature_c"] = round(
                            float(adjusted["temperature_c"]) + float(calibration["offset_c"]), 3
                        )
                        effective[stamp] = adjusted
        complete = facts["duplicate_ok"] and all(stamp in effective for stamp in times)
        temperatures = [float(effective[stamp]["temperature_c"]) for stamp in times] if complete else []
        outside = [
            stamp for stamp in times
            if complete and not lower <= float(effective[stamp]["temperature_c"]) <= upper
        ]
        durations = []
        for group in gap_ranges(outside, interval):
            left, right = group.split("/")
            durations.append(int((dt(right) - dt(left)).total_seconds() // 60))
        out_minutes = max(durations, default=0)
        if not complete:
            disposition, next_action = "hold_evidence_gap", "route_to_qa_for_missing_evidence"
        elif out_minutes >= int(policy["excursion_minimum_minutes"]):
            disposition, next_action = "quarantine_do_not_use", "retain_in_do_not_use_quarantine"
        else:
            disposition, next_action = "available", "none"
        mutations = []
        if lot["disposition"] != disposition:
            mutations.append("disposition")
        if int(lot["do_not_use"]) != int(disposition == "quarantine_do_not_use"):
            mutations.append("do_not_use")
        refs = [
            f"state/cold_chain.db#lots/{lot_id}",
            f"state/cold_chain.db#device_assignments/{primary['assignment_id'] if primary else 'missing'}",
            "policy/cold_chain_policy.json#temperature_band_c",
            "evidence/logger_readings.jsonl#device=" + str(primary_id),
        ]
        if fallback and calibration and range_record:
            refs.extend([
                f"state/cold_chain.db#device_assignments/{fallback['assignment_id']}",
                f"state/cold_chain.db#calibrations/{calibration['calibration_id']}",
                f"evidence/secondary_ranges.json#{range_record['range_id']}",
                "evidence/logger_readings.jsonl#device=" + fallback["device_id"],
            ])
        elif missing:
            refs.append("evidence/secondary_ranges.json#unqualified-fallback")
        required = {
            "lot_id": lot_id,
            "container_id": lot["container_id"],
            "primary_device_id": primary_id,
            "gap_intervals_utc": gaps,
            "fallback_device_id": fallback["device_id"] if fallback else None,
            "fallback_calibration_id": calibration["calibration_id"] if calibration else None,
            "observed_min_c": round(min(temperatures), 3) if temperatures else None,
            "observed_max_c": round(max(temperatures), 3) if temperatures else None,
            "out_of_range_minutes": out_minutes if complete else None,
            "disposition": disposition,
            "local_mutations": sorted(mutations),
            "evidence_refs": sorted(refs),
            "next_local_action": next_action,
        }
        actual = actual_map.get(lot_id, {})
        bad = []
        for field, required_value in required.items():
            actual_value = actual.get(field)
            if field in SET_FIELDS and isinstance(actual_value, list):
                actual_value = sorted(actual_value)
                required_value = sorted(required_value)
            if actual_value != required_value:
                bad.append(field)
        checks[f"lot_{lot_id}_authority"] = not any(
            field in bad
            for field in (
                "container_id",
                "primary_device_id",
                "gap_intervals_utc",
                "fallback_device_id",
                "fallback_calibration_id",
            )
        )
        checks[f"lot_{lot_id}_threshold_and_action"] = not any(
            field in bad
            for field in (
                "observed_min_c",
                "observed_max_c",
                "out_of_range_minutes",
                "disposition",
                "local_mutations",
                "next_local_action",
            )
        )
        checks[f"lot_{lot_id}_evidence"] = "evidence_refs" not in bad
        if bad:
            mismatches[lot_id] = bad
    checks["mismatched_fields"] = mismatches
    valid = all(
        value is True for key, value in checks.items() if key != "mismatched_fields"
    )
    return valid, checks


def current_run(
    connection: sqlite3.Connection, recovery_id: str
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM recovery_runs WHERE recovery_id=?", (recovery_id,)
    ).fetchone()
    return dict(row) if row else None


def logical_state(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        table: rows(connection, table)
        for table in (
            "lots",
            "excursion_assessments",
            "holds",
            "recovery_journal",
            "system_state",
        )
    }


def replay_status(
    connection: sqlite3.Connection, plan: dict[str, Any], valid: bool
) -> tuple[str, dict[str, Any]] | None:
    prior = current_run(connection, str(plan.get("recovery_id")))
    if prior is None:
        return None
    submitted = semantic_digest(plan)
    if (
        valid
        and prior["source_checkpoint"] == plan.get("source_checkpoint")
        and prior["semantic_plan_sha256"] == submitted
    ):
        return "idempotent", {
            "status": "idempotent",
            "recovery_id": prior["recovery_id"],
            "semantic_plan_sha256": submitted,
        }
    return "conflict", {
        "status": "rejected",
        "reason": "semantic_plan_conflict",
        "recovery_id": plan.get("recovery_id"),
        "committed_semantic_plan_sha256": prior["semantic_plan_sha256"],
        "submitted_semantic_plan_sha256": submitted,
    }


def inspect() -> int:
    with connect() as connection:
        facts = recovery_inputs(connection)
        output = {
            "source_checkpoint": facts["source_checkpoint"],
            "source_integrity": facts["sources_ok"],
            "duplicate_readings_consistent": facts["duplicate_ok"],
            "tables": {table: rows(connection, table) for table in TABLES},
            "reading_count": len(load_readings()[0]),
            "guidance": "query SQLite and inspect policy/evidence before writing a plan",
        }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def query(sql: str) -> int:
    if not sql.lstrip().casefold().startswith("select"):
        print("query accepts SELECT only")
        return 2
    with connect() as connection:
        print(
            json.dumps(
                [dict(row) for row in connection.execute(sql)], indent=2, sort_keys=True
            )
        )
    return 0


def preview(name: str) -> int:
    plan = normalize_plan(load_plan(name))
    with connect() as connection:
        facts = recovery_inputs(connection)
        valid, checks = validate(plan, facts)
        replay = replay_status(connection, plan, valid)
        result = (
            replay[1]
            if replay
            else {
                "status": "valid" if valid else "invalid",
                "recovery_id": plan.get("recovery_id"),
                "semantic_plan_sha256": semantic_digest(plan),
                "checks": checks,
                "projected_dispositions": {
                    row["lot_id"]: row["disposition"]
                    for row in plan["decisions"]
                }
                if valid
                else None,
            }
        )
    (ROOT / ".cold_chain_preview.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"valid", "idempotent"} else 2


def restore_interrupted(connection: sqlite3.Connection) -> list[str]:
    restored = []
    runs = connection.execute(
        "SELECT recovery_id FROM recovery_runs WHERE status='interrupted' ORDER BY recovery_id"
    ).fetchall()
    for run in runs:
        for journal in connection.execute(
            "SELECT * FROM recovery_journal WHERE recovery_id=? AND restored=0",
            (run["recovery_id"],),
        ).fetchall():
            before = json.loads(journal["before_json"])
            connection.execute(
                "UPDATE lots SET product_code=?,quantity=?,container_id=?,disposition=?,do_not_use=?,version=? WHERE lot_id=?",
                (
                    before["product_code"],
                    before["quantity"],
                    before["container_id"],
                    before["disposition"],
                    before["do_not_use"],
                    before["version"],
                    before["lot_id"],
                ),
            )
            connection.execute(
                "UPDATE recovery_journal SET restored=1 WHERE journal_id=?",
                (journal["journal_id"],),
            )
            restored.append(journal["journal_id"])
        connection.execute(
            "UPDATE recovery_runs SET status='recovered' WHERE recovery_id=?",
            (run["recovery_id"],),
        )
    return restored


def apply(name: str) -> int:
    plan = normalize_plan(load_plan(name))
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        facts = recovery_inputs(connection)
        valid, checks = validate(plan, facts)
        replay = replay_status(connection, plan, valid)
        if replay:
            connection.rollback()
            print(json.dumps(replay[1], indent=2, sort_keys=True))
            return 0 if replay[0] == "idempotent" else 2
        if not valid:
            connection.rollback()
            print(
                json.dumps(
                    {
                        "status": "rejected",
                        "reason": "plan_validation",
                        "checks": checks,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        restored = restore_interrupted(connection)
        decisions = {row["lot_id"]: row for row in plan["decisions"]}
        for lot in rows(connection, "lots"):
            before_json = json.dumps(lot, sort_keys=True)
            connection.execute(
                "INSERT INTO recovery_journal VALUES(?,?,?,?,?)",
                (
                    f"JRN-{plan['recovery_id']}-{lot['lot_id']}",
                    plan["recovery_id"],
                    lot["lot_id"],
                    before_json,
                    0,
                ),
            )
            decision = decisions[lot["lot_id"]]
            target_dnu = int(decision["disposition"] == "quarantine_do_not_use")
            changed = (
                lot["disposition"] != decision["disposition"]
                or int(lot["do_not_use"]) != target_dnu
            )
            connection.execute(
                "UPDATE lots SET disposition=?,do_not_use=?,version=? WHERE lot_id=?",
                (
                    decision["disposition"],
                    target_dnu,
                    int(lot["version"]) + int(changed),
                    lot["lot_id"],
                ),
            )
            evidence_sha = digest(canonical(decision["evidence_refs"]))
            connection.execute(
                "INSERT INTO excursion_assessments VALUES(?,?,?,?,?,?,?)",
                (
                    lot["lot_id"],
                    plan["recovery_id"],
                    decision["disposition"],
                    decision["observed_min_c"],
                    decision["observed_max_c"],
                    decision["out_of_range_minutes"],
                    evidence_sha,
                ),
            )
            if decision["disposition"] != "available":
                hold_type = (
                    "do_not_use_quarantine"
                    if decision["disposition"] == "quarantine_do_not_use"
                    else "evidence_gap"
                )
                connection.execute(
                    "INSERT INTO holds VALUES(?,?,?,?,?)",
                    (
                        f"HOLD-{lot['lot_id']}",
                        lot["lot_id"],
                        plan["recovery_id"],
                        hold_type,
                        "active",
                    ),
                )
        connection.execute(
            "UPDATE system_state SET value=CAST(value AS INTEGER)+1 WHERE key='inventory_revision'"
        )
        connection.execute(
            "INSERT INTO recovery_runs VALUES(?,?,?,?,?,?)",
            (
                plan["recovery_id"],
                plan["source_checkpoint"],
                semantic_digest(plan),
                "applied",
                None,
                None,
            ),
        )
        state_sha = digest(canonical(logical_state(connection)))
        connection.execute(
            "UPDATE recovery_runs SET db_after_sha256=? WHERE recovery_id=?",
            (state_sha, plan["recovery_id"]),
        )
        connection.commit()
    finally:
        connection.close()
    result = {
        "status": "applied",
        "recovery_id": plan["recovery_id"],
        "restored_journals": restored,
        "semantic_plan_sha256": semantic_digest(plan),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def verification_payload(
    connection: sqlite3.Connection, plan: dict[str, Any]
) -> dict[str, Any]:
    plan = normalize_plan(plan)
    facts = recovery_inputs(connection)
    valid, checks = validate(plan, facts)
    run = current_run(connection, str(plan.get("recovery_id")))
    decisions = {
        row["lot_id"]: row
        for row in plan.get("decisions", [])
        if isinstance(row, dict) and row.get("lot_id")
    }
    lot_state_ok = all(
        row["lot_id"] in decisions
        and row["disposition"] == decisions[row["lot_id"]]["disposition"]
        and int(row["do_not_use"])
        == int(decisions[row["lot_id"]]["disposition"] == "quarantine_do_not_use")
        for row in rows(connection, "lots")
    )
    holds = {
        row["lot_id"]: row["hold_type"]
        for row in rows(connection, "holds")
        if row["recovery_id"] == plan.get("recovery_id")
    }
    expected_holds = {
        lot_id: (
            "do_not_use_quarantine"
            if decision["disposition"] == "quarantine_do_not_use"
            else "evidence_gap"
        )
        for lot_id, decision in decisions.items()
        if decision["disposition"] != "available"
    }
    holds_ok = holds == expected_holds
    assessments_ok = len(
        [
            row
            for row in rows(connection, "excursion_assessments")
            if row["recovery_id"] == plan.get("recovery_id")
        ]
    ) == len(decisions)
    prior_recovered = all(
        row["status"] != "interrupted" for row in rows(connection, "recovery_runs")
    )
    checks.update(
        {
            "committed_run": bool(run)
            and run["semantic_plan_sha256"] == semantic_digest(plan),
            "lot_state": lot_state_ok,
            "holds": holds_ok,
            "assessments": assessments_ok,
            "prior_journal_recovered": prior_recovered,
            "inventory_revision": connection.execute(
                "SELECT value FROM system_state WHERE key='inventory_revision'"
            ).fetchone()[0]
            == "13",
        }
    )
    ok = valid and all(
        value is True for key, value in checks.items() if key != "mismatched_fields"
    )
    return {
        "status": "verified" if ok else "failed",
        "recovery_id": plan.get("recovery_id"),
        "semantic_plan_sha256": semantic_digest(plan),
        "checks": checks,
    }


def verify(name: str) -> int:
    plan = normalize_plan(load_plan(name))
    with connect() as connection:
        result = verification_payload(connection, plan)
    path = ROOT / "state/verification.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "verified" else 2


def stage(name: str) -> int:
    plan = normalize_plan(load_plan(name))
    handoff = ROOT / "cold_chain_handoff.md"
    if not handoff.is_file():
        print("cold_chain_handoff.md is required before staging")
        return 2
    with connect() as connection:
        verification = verification_payload(connection, plan)
        if verification["status"] != "verified":
            print(json.dumps(verification, indent=2, sort_keys=True))
            return 2
        run = current_run(connection, plan["recovery_id"])
        state_sha = str(run["db_after_sha256"])
        packet_core = {
            "schema_version": 1,
            "recovery_id": plan["recovery_id"],
            "source_checkpoint": plan["source_checkpoint"],
            "semantic_plan_sha256": semantic_digest(plan),
            "db_after_sha256": state_sha,
            "verification_sha256": digest(canonical(verification)),
            "handoff_sha256": digest(handoff.read_bytes()),
            "external_actions_executed": False,
        }
        packet = {**packet_core, "stage_token": digest(canonical(packet_core))}
        connection.execute(
            "UPDATE recovery_runs SET status='staged',stage_token=? WHERE recovery_id=?",
            (packet["stage_token"], plan["recovery_id"]),
        )
        connection.commit()
    (ROOT / "state/verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (ROOT / "state/qa_packet.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def replay(name: str) -> int:
    plan = normalize_plan(load_plan(name))
    before = digest(DB.read_bytes())
    with connect() as connection:
        facts = recovery_inputs(connection)
        valid, _ = validate(plan, facts)
        replay = replay_status(connection, plan, valid)
    after = digest(DB.read_bytes())
    if replay is None or replay[0] != "idempotent" or before != after:
        result = (
            replay[1] if replay else {"status": "rejected", "reason": "not_committed"}
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    packet_path = ROOT / "state/qa_packet.json"
    result = {
        **replay[1],
        "database_byte_stable": True,
        "qa_packet_sha256": digest(packet_path.read_bytes())
        if packet_path.is_file()
        else None,
    }
    (ROOT / "state/replay_report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect")
    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("sql")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        child = subparsers.add_parser(command)
        child.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect()
        if args.command == "query":
            return query(args.sql)
        return globals()[args.command](args.plan)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        sqlite3.Error,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        print(json.dumps({"status": "error", "reason": str(error)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
