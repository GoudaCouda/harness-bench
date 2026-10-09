#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/network.db"
POLICY = ROOT / "policy/isolation_policy.json"
MANIFEST = ROOT / "policy/source_manifest.json"
EVENTS = ROOT / "evidence/telemetry_events.jsonl"
PREVIEW = ROOT / ".isolation_preview.json"
SET_FIELDS = {"reason_codes", "impacted_zone_ids", "local_mutations", "evidence_refs"}
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "work_order_id",
    "selected_boundary_id", "valve_decisions", "delivery_dispositions",
    "impact_summary", "external_actions_executed",
}
VALVE_FIELDS = {
    "valve_id", "observed_operability", "desired_position", "disposition",
    "reason_codes", "impacted_zone_ids", "local_mutations", "next_local_action",
    "evidence_refs",
}
DELIVERY_FIELDS = {"delivery_id", "event_id", "valve_id", "source_sequence", "disposition"}
SUMMARY_FIELDS = {
    "selected_boundary_id", "affected_connections", "critical_service_outages",
    "valves_to_close", "unavailable_valves", "protected_valves", "quarantined_deliveries",
}
QUERY_TABLES = {
    "system_state", "work_orders", "valves", "boundaries", "boundary_valves",
    "recovery_runs", "recovery_journal", "valve_projections",
}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(con: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    con.row_factory = sqlite3.Row
    return [dict(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()]


def _events() -> list[dict[str, Any]]:
    return [json.loads(line) for line in EVENTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def _manifest_ok() -> tuple[bool, list[str]]:
    manifest = _load(MANIFEST)
    changed = []
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        if not path.is_file() or _sha(path) != expected:
            changed.append(relative)
    return not changed, changed


def _source_checkpoint() -> str:
    ok, changed = _manifest_ok()
    if not ok:
        raise ValueError(f"source manifest mismatch: {changed}")
    with sqlite3.connect(DB) as con:
        protected = {
            "system_state": _rows(con, "system_state"),
            "work_orders": _rows(con, "work_orders"),
            "valves": [
                {key: value for key, value in row.items() if key not in {"local_desired_position", "local_disposition"}}
                for row in _rows(con, "valves")
            ],
            "boundaries": _rows(con, "boundaries"),
            "boundary_valves": _rows(con, "boundary_valves"),
        }
    payload = {"manifest": _load(MANIFEST), "database_sources": protected}
    return "sha256:" + hashlib.sha256(_canonical(payload)).hexdigest()


def _event_body(row: dict[str, Any]) -> bytes:
    return _canonical({key: value for key, value in row.items() if key != "delivery_id"})


def _derive_deliveries(valves: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    deliveries = _events()
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deliveries:
        by_event[row["event_id"]].append(row)
    identity_collisions = {
        event_id for event_id, rows in by_event.items() if len({_event_body(row) for row in rows}) > 1
    }
    first_delivery: dict[str, str] = {}
    for row in deliveries:
        first_delivery.setdefault(row["event_id"], row["delivery_id"])
    by_slot: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in deliveries:
        if row["event_id"] not in identity_collisions:
            by_slot[(row["valve_id"], row["source_sequence"])].add(row["event_id"])
    sequence_collisions = {slot for slot, identities in by_slot.items() if len(identities) > 1}

    result = []
    accepted: dict[str, tuple[int, str]] = {}
    for row in deliveries:
        valve = valves.get(row["valve_id"])
        slot = (row["valve_id"], row["source_sequence"])
        if row["event_id"] in identity_collisions:
            disposition = "quarantine_identity_collision"
        elif slot in sequence_collisions:
            disposition = "quarantine_sequence_collision"
        elif valve is None:
            disposition = "ignore_unknown_valve"
        elif valve["maintenance_locked"]:
            disposition = "ignore_protected_valve"
        elif row["source_sequence"] <= valve["high_water_sequence"]:
            disposition = "ignore_stale"
        elif first_delivery[row["event_id"]] != row["delivery_id"]:
            disposition = "ignore_exact_redelivery"
        else:
            disposition = "apply_observation"
            accepted[row["valve_id"]] = (row["source_sequence"], row["payload"]["operability"])
        result.append({
            "delivery_id": row["delivery_id"], "event_id": row["event_id"],
            "valve_id": row["valve_id"], "source_sequence": row["source_sequence"],
            "disposition": disposition,
        })
    return result, {valve_id: value for valve_id, (_, value) in accepted.items()}


def _validation_context() -> dict[str, Any]:
    """Load rule inputs for validation without materializing a target plan."""
    policy = _load(POLICY)
    checkpoint = _source_checkpoint()
    with sqlite3.connect(DB) as con:
        valves = {row["valve_id"]: row for row in _rows(con, "valves")}
        boundaries = {row["boundary_id"]: row for row in _rows(con, "boundaries")}
        members: dict[str, list[str]] = defaultdict(list)
        for row in _rows(con, "boundary_valves"):
            members[row["boundary_id"]].append(row["valve_id"])
    deliveries, accepted = _derive_deliveries(valves)
    observed = {key: accepted.get(key, row["base_operability"]) for key, row in valves.items()}

    admissible = []
    for boundary_id, boundary in boundaries.items():
        valve_ids = members[boundary_id]
        closable = all(observed[valve_id] == "operable" for valve_id in valve_ids)
        unlocked = all(not valves[valve_id]["maintenance_locked"] for valve_id in valve_ids)
        no_critical = boundary["critical_service_outages"] <= policy["admissibility"]["maximum_critical_service_outages"]
        if closable and unlocked and no_critical:
            admissible.append((boundary["affected_connections"], boundary_id))
    if not admissible:
        raise ValueError("no admissible isolation boundary")
    _, selected = min(admissible)
    selected_members = set(members[selected])
    selected_zones = json.loads(boundaries[selected]["impacted_zone_ids_json"])

    return {
        "policy": policy,
        "checkpoint": checkpoint,
        "valves": valves,
        "boundaries": boundaries,
        "members": members,
        "delivery_rules": {row["delivery_id"]: row for row in deliveries},
        "accepted_observations": accepted,
        "observed": observed,
        "selected": selected,
        "selected_members": selected_members,
        "selected_zones": selected_zones,
    }


def _normalize(plan: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(plan))
    value["valve_decisions"] = sorted(value.get("valve_decisions", []), key=lambda row: str(row.get("valve_id", "")))
    for row in value["valve_decisions"]:
        for field in SET_FIELDS:
            if isinstance(row.get(field), list):
                row[field] = sorted(set(str(item) for item in row[field]))
    value["delivery_dispositions"] = sorted(value.get("delivery_dispositions", []), key=lambda row: str(row.get("delivery_id", "")))
    for field in ("valves_to_close", "unavailable_valves", "protected_valves", "quarantined_deliveries"):
        if isinstance(value.get("impact_summary", {}).get(field), list):
            value["impact_summary"][field] = sorted(set(str(item) for item in value["impact_summary"][field]))
    return value


def _plan_hash(plan: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(_normalize(plan))).hexdigest()


def _diagnostics(actual: dict[str, Any]) -> dict[str, Any]:
    context = _validation_context()
    policy = context["policy"]
    selected = context["selected"]
    boundaries = context["boundaries"]
    valves = context["valves"]
    observed = context["observed"]
    selected_members = context["selected_members"]
    selected_zones = context["selected_zones"]
    expected_globals = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": context["checkpoint"],
        "work_order_id": policy["work_order_id"],
        "selected_boundary_id": selected,
        "impact_summary": {
            "selected_boundary_id": selected,
            "affected_connections": boundaries[selected]["affected_connections"],
            "critical_service_outages": boundaries[selected]["critical_service_outages"],
            "valves_to_close": sorted(selected_members),
            "unavailable_valves": sorted(key for key, value in observed.items() if value != "operable"),
            "protected_valves": sorted(key for key, value in valves.items() if value["maintenance_locked"] or value["critical_feed"]),
            "quarantined_deliveries": sorted(key for key, row in context["delivery_rules"].items() if row["disposition"].startswith("quarantine_")),
        },
        "external_actions_executed": False,
    }
    global_mismatches = sorted(field for field, expected in expected_globals.items() if actual.get(field) != expected)
    if set(actual) != PLAN_FIELDS:
        global_mismatches.append("top_level_schema")
    actual_valves = {row.get("valve_id"): row for row in actual.get("valve_decisions", []) if isinstance(row, dict)}
    valve_diagnostics = {}
    for key in sorted(valves):
        row = actual_valves.get(key, {})
        mismatches = []
        if set(row) != VALVE_FIELDS:
            mismatches.append("schema")
        valve = valves[key]
        if valve["maintenance_locked"]:
            disposition, reason, next_action = "preserve_maintenance_lock", "maintenance_lock", "coordinate_lock_owner"
        elif observed[key] != "operable":
            disposition, reason, next_action = "preserve_unavailable", "unavailable", "field_assessment_required"
        elif valve["critical_feed"]:
            disposition, reason, next_action = "preserve_critical_feed", "critical_feed", "critical_service_review"
        elif key in selected_members:
            disposition, reason, next_action = "stage_close", "selected_boundary", "field_authorization_required"
        else:
            disposition, reason, next_action = "preserve_open", "outside_boundary", "none"
        desired = "closed" if disposition == "stage_close" else valve["physical_position"]
        refs = [f"state/network.db#valves:{key}", "policy/isolation_policy.json#reason_precedence"]
        if key in selected_members:
            refs.extend([f"state/network.db#boundaries:{selected}", f"state/network.db#boundary_valves:{selected}/{key}"])
        if key in context["accepted_observations"]:
            delivery_id = next(
                delivery_id for delivery_id, delivery in context["delivery_rules"].items()
                if delivery["valve_id"] == key and delivery["disposition"] == "apply_observation"
            )
            refs.append(f"evidence/telemetry_events.jsonl#{delivery_id}")
        expected_fields = {
            "valve_id": key,
            "observed_operability": observed[key],
            "desired_position": desired,
            "disposition": disposition,
            "reason_codes": [reason],
            "impacted_zone_ids": selected_zones if key in selected_members else [],
            "local_mutations": [f"local_desired_position={desired}", f"local_disposition={disposition}"],
            "next_local_action": next_action,
            "evidence_refs": refs,
        }
        for field in VALVE_FIELDS - {"valve_id"}:
            left, right = row.get(field), expected_fields[field]
            if field in SET_FIELDS:
                left = sorted(set(left)) if isinstance(left, list) else left
                right = sorted(set(right))
            if left != right:
                mismatches.append(field)
        if mismatches:
            valve_diagnostics[key] = {"mismatches": sorted(set(mismatches))}
    extras = sorted(set(actual_valves) - set(valves))
    if extras:
        global_mismatches.append("extra_valve_ids:" + ",".join(extras))

    actual_events = {row.get("delivery_id"): row for row in actual.get("delivery_dispositions", []) if isinstance(row, dict)}
    event_diagnostics = {}
    for key, expected_row in sorted(context["delivery_rules"].items()):
        row = actual_events.get(key, {})
        mismatches = []
        if set(row) != DELIVERY_FIELDS:
            mismatches.append("schema")
        for field in DELIVERY_FIELDS - {"delivery_id"}:
            if row.get(field) != expected_row[field]:
                mismatches.append(field)
        if mismatches:
            event_diagnostics[key] = {"mismatches": sorted(set(mismatches))}
    extras = sorted(set(actual_events) - set(context["delivery_rules"]))
    if extras:
        global_mismatches.append("extra_delivery_ids:" + ",".join(extras))
    return {
        "ok": not global_mismatches and not valve_diagnostics and not event_diagnostics,
        "global_mismatches": sorted(set(global_mismatches)),
        "valve_diagnostics": valve_diagnostics,
        "delivery_diagnostics": event_diagnostics,
    }


def _read_plan(path: str) -> dict[str, Any]:
    value = _load(ROOT / path)
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    return value


def preview(path: str) -> int:
    plan = _read_plan(path)
    diagnostics = _diagnostics(plan)
    diagnostics.update({"recovery_id": plan.get("recovery_id"), "source_checkpoint": _source_checkpoint(), "plan_hash": _plan_hash(plan)})
    _write(PREVIEW, diagnostics)
    print(json.dumps(diagnostics, indent=2, sort_keys=True))
    return 0 if diagnostics["ok"] else 1


def apply(path: str) -> int:
    plan = _read_plan(path)
    if plan.get("source_checkpoint") != _source_checkpoint():
        raise ValueError("stale source_checkpoint")
    diagnostics = _diagnostics(plan)
    if not diagnostics["ok"]:
        _write(PREVIEW, {**diagnostics, "source_checkpoint": _source_checkpoint(), "plan_hash": _plan_hash(plan)})
        raise ValueError("plan does not pass preview; inspect object diagnostics")
    normalized_hash = _plan_hash(plan)
    recovery_id = plan["recovery_id"]
    with sqlite3.connect(DB) as con:
        existing = con.execute("SELECT plan_hash FROM recovery_runs WHERE recovery_id=?", (recovery_id,)).fetchone()
        if existing:
            if existing[0] != normalized_hash:
                raise ValueError("conflicting semantic plan for recovery identity")
            print("already applied with the same semantic plan")
            return 0
        con.execute("BEGIN IMMEDIATE")
        journals = con.execute("SELECT journal_id,recovery_id,valve_id,before_json FROM recovery_journal WHERE restored=0 ORDER BY journal_id").fetchall()
        for journal_id, old_recovery, valve_id, before_json in journals:
            before = json.loads(before_json)
            con.execute("UPDATE valves SET local_desired_position=?,local_disposition=? WHERE valve_id=?", (before["local_desired_position"], before["local_disposition"], valve_id))
            con.execute("DELETE FROM valve_projections WHERE recovery_id=? AND valve_id=?", (old_recovery, valve_id))
            con.execute("UPDATE recovery_runs SET status='rolled_back' WHERE recovery_id=?", (old_recovery,))
            con.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
        for row in plan["valve_decisions"]:
            con.execute("UPDATE valves SET local_desired_position=?,local_disposition=? WHERE valve_id=?", (row["desired_position"], row["disposition"], row["valve_id"]))
            con.execute("INSERT INTO valve_projections VALUES (?,?,?,?,?,?)", (recovery_id, row["valve_id"], normalized_hash, row["desired_position"], row["disposition"], row["observed_operability"]))
        con.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?)", (recovery_id, plan["source_checkpoint"], normalized_hash, "applied", plan["selected_boundary_id"]))
        con.commit()
    _write(ROOT / "state/recovery_receipt.json", {
        "recovery_id": recovery_id, "source_checkpoint": plan["source_checkpoint"],
        "plan_hash": normalized_hash, "restored_journal_ids": [row[0] for row in journals],
        "projection_count": len(plan["valve_decisions"]), "status": "applied_local_projection",
    })
    print("applied local projection")
    return 0


def _verification(plan: dict[str, Any]) -> dict[str, Any]:
    normalized_hash = _plan_hash(plan)
    with sqlite3.connect(DB) as con:
        run = con.execute("SELECT source_checkpoint,plan_hash,status,selected_boundary_id FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        projections = con.execute("SELECT valve_id,desired_position,disposition,operability,plan_hash FROM valve_projections WHERE recovery_id=? ORDER BY valve_id", (plan["recovery_id"],)).fetchall()
        open_journals = con.execute("SELECT COUNT(*) FROM recovery_journal WHERE restored=0").fetchone()[0]
        physical = con.execute("SELECT valve_id,physical_position FROM valves ORDER BY valve_id").fetchall()
    expected_projection = [(row["valve_id"], row["desired_position"], row["disposition"], row["observed_operability"], normalized_hash) for row in sorted(plan["valve_decisions"], key=lambda item: item["valve_id"])]
    checks = {
        "source_checkpoint_current": plan.get("source_checkpoint") == _source_checkpoint(),
        "run_closed": run == (plan["source_checkpoint"], normalized_hash, "applied", plan["selected_boundary_id"]),
        "journal_restored": open_journals == 0,
        "projections_reconciled": projections == expected_projection,
        "physical_positions_unchanged": all(position == "open" for _, position in physical),
    }
    return {"recovery_id": plan["recovery_id"], "plan_hash": normalized_hash, "checks": checks, "verified": all(checks.values())}


def verify(path: str) -> int:
    result = _verification(_read_plan(path))
    _write(ROOT / "state/verification.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verified"] else 1


def stage(path: str) -> int:
    plan = _read_plan(path)
    verification = _verification(plan)
    handoff = ROOT / "isolation_handoff.md"
    if not verification["verified"] or not handoff.is_file() or handoff.stat().st_size < 200:
        raise ValueError("verified plan and substantive isolation_handoff.md required")
    packet = {
        "recovery_id": plan["recovery_id"], "work_order_id": plan["work_order_id"],
        "selected_boundary_id": plan["selected_boundary_id"], "source_checkpoint": plan["source_checkpoint"],
        "plan_hash": _plan_hash(plan), "status": "staged_offline_review_only",
        "external_actions_executed": False,
    }
    packet_path = ROOT / "staging/isolation_review_packet.json"
    _write(packet_path, packet)
    _write(ROOT / "staging/packet_manifest.json", {
        "schema_version": 1,
        "files": {
            "isolation_handoff.md": _sha(handoff),
            "staging/isolation_review_packet.json": _sha(packet_path),
        },
    })
    print("staged offline review packet")
    return 0


def replay(path: str) -> int:
    plan = _read_plan(path)
    if plan.get("source_checkpoint") != _source_checkpoint():
        raise ValueError("stale source_checkpoint")
    normalized_hash = _plan_hash(plan)
    before = _sha(DB)
    with sqlite3.connect(DB) as con:
        row = con.execute("SELECT plan_hash FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    if row is None or row[0] != normalized_hash:
        raise ValueError("missing recovery or conflicting semantic replay")
    after = _sha(DB)
    report = {
        "recovery_id": plan["recovery_id"], "plan_hash": normalized_hash,
        "semantic_noop": True, "database_unchanged": before == after,
        "database_sha256": after,
    }
    _write(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def inspect() -> int:
    with sqlite3.connect(DB) as con:
        payload = {
            "source_checkpoint": _source_checkpoint(),
            "policy": _load(POLICY),
            "counts": {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in sorted(QUERY_TABLES)},
            "open_journals": _rows(con, "recovery_journal"),
            "query_tables": sorted(QUERY_TABLES),
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def query(table: str) -> int:
    if table not in QUERY_TABLES:
        raise ValueError("allowed tables: " + ", ".join(sorted(QUERY_TABLES)))
    with sqlite3.connect(DB) as con:
        print(json.dumps(_rows(con, table), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded offline water-isolation projection controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("table")
    for name in ("preview", "apply", "verify", "stage", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect()
        if args.command == "query":
            return query(args.table)
        return globals()[args.command](args.plan)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
