#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from pitr_lib import ROOT, backup, canonical_sha, derived_plan_core, final_state, input_digests, load, normalized_plan, probe_document, receipt, required_segments, target, validate_plan, write_json


STATE = "state/recovery_state.json"


def fail(*errors: str) -> int:
    print(json.dumps({"status": "rejected", "errors": list(errors)}, indent=2))
    return 2


def read_plan(relative: str) -> dict:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("plan must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Protected synthetic PostgreSQL PITR drill controller")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "backups", "timelines", "incident"):
        sub.add_parser(name)
    backup_cmd = sub.add_parser("backup")
    backup_cmd.add_argument("--id", required=True)
    wal = sub.add_parser("wal")
    wal.add_argument("--timeline", required=True, type=int)
    verify = sub.add_parser("verify-backup")
    verify.add_argument("--id", required=True)
    for name in ("validate-plan", "restore", "close-gate", "replay"):
        command = sub.add_parser(name)
        command.add_argument("--plan", required=True)
    sub.add_parser("probe")
    args = parser.parse_args()
    state = load(STATE)

    if args.command == "status":
        print(json.dumps({**state, "input_sha256": input_digests()}, indent=2, sort_keys=True))
        return 0
    if args.command == "backups":
        rows = [{"backup_id": row["backup_id"], "timeline": row["timeline"], "ended_at": row["ended_at"], "system_identifier": row["system_identifier"], "manifest_status": row["manifest_status"], "file_status": row["file_status"], "wal_manifest_status": row["wal_manifest_status"]} for row in load("evidence/backups.json")["backups"]]
        print(json.dumps({"backups": rows}, indent=2, sort_keys=True))
        return 0
    if args.command == "timelines":
        print(json.dumps(load("evidence/timeline_history.json"), indent=2, sort_keys=True))
        return 0
    if args.command == "incident":
        print(json.dumps({"incident": load("evidence/incident.json"), "restore_points": load("evidence/wal_archive.json")["restore_points"], "transactions_near_target": load("evidence/wal_archive.json")["transactions"]}, indent=2, sort_keys=True))
        return 0
    if args.command == "backup":
        row = backup(args.id)
        if row is None:
            return fail(f"unknown backup: {args.id}")
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0
    if args.command == "wal":
        archive = load("evidence/wal_archive.json")
        print(json.dumps({"timeline": args.timeline, "segments": [row for row in archive["segments"] if row["timeline"] == args.timeline], "restore_points": [row for row in archive["restore_points"] if row["timeline"] == args.timeline], "transactions": [row for row in archive["transactions"] if row["timeline"] == args.timeline]}, indent=2, sort_keys=True))
        return 0
    if args.command == "verify-backup":
        row = backup(args.id)
        if row is None:
            return fail(f"unknown backup: {args.id}")
        incident = load("evidence/incident.json")
        errors = []
        if row["system_identifier"] != incident["system_identifier"]:
            errors.append("system identifier mismatch")
        if any(row[field] != "verified" for field in ("manifest_status", "file_status", "wal_manifest_status")):
            errors.append("backup manifest, files, and manifest WAL must all verify")
        if row["timeline"] != incident["affected_timeline"]:
            errors.append("backup belongs to a divergent timeline, not the incident history")
        if errors:
            return fail(*errors)
        state["verified_backup_id"] = row["backup_id"]
        state["phase"] = "backup_verified"
        write_json(STATE, state)
        print(json.dumps({"status": "pass", "backup_id": row["backup_id"], "timeline": row["timeline"], "required_wal_segments": required_segments()}, indent=2))
        return 0
    if args.command in {"validate-plan", "restore", "close-gate", "replay"}:
        try:
            plan = read_plan(args.plan)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return fail(str(exc))
        errors = validate_plan(plan)
        if errors:
            return fail(*errors)
    if args.command == "validate-plan":
        if state.get("verified_backup_id") != derived_plan_core()["backup_id"]:
            return fail("verify the selected backup before validating the plan")
        state["phase"] = "plan_validated"
        state["plan_sha256"] = canonical_sha(normalized_plan(plan))
        write_json(STATE, state)
        print(json.dumps({"status": "pass", "plan_sha256": state["plan_sha256"], "wal_segment_count": len(required_segments())}, indent=2))
        return 0
    if args.command == "restore":
        if state.get("phase") != "plan_validated" or state.get("plan_sha256") != canonical_sha(normalized_plan(plan)):
            return fail("restore requires the currently validated plan")
        point = target()
        state.update(phase="isolated_restore_complete", restored_timeline=point["timeline"], restored_target_name=point["name"], restored_target_lsn=point["lsn"], probe_runs=0, probe_sha256=None)
        write_json(STATE, state)
        print(json.dumps({"status": "pass", "scope": "isolated", "target_name": point["name"], "target_lsn": point["lsn"], "production_changed": False}, indent=2))
        return 0
    if args.command == "probe":
        if state.get("phase") not in {"isolated_restore_complete", "probes_complete"}:
            return fail("probe requires a completed isolated restore")
        runs = min(int(state.get("probe_runs", 0)) + 1, 2)
        document = probe_document(runs)
        state["probe_runs"] = runs
        state["probe_sha256"] = canonical_sha(document) if runs >= 2 else None
        state["phase"] = "probes_complete" if runs >= 2 else "isolated_restore_complete"
        write_json("work/probe_report.json", document)
        write_json(STATE, state)
        print(json.dumps({"status": "pass", "run_count": runs, "identical_passes": runs >= 2, "check_count": len(document["results"])}, indent=2))
        return 0
    if args.command == "close-gate":
        expected_probe = probe_document(2)
        try:
            actual_probe = json.loads((ROOT / "work/probe_report.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return fail("complete probe report is missing")
        if state.get("phase") != "probes_complete" or state.get("probe_runs") != 2 or actual_probe != expected_probe or state.get("probe_sha256") != canonical_sha(expected_probe):
            return fail("two complete identical probe passes are required")
        write_json(STATE, final_state(plan, False))
        write_json("work/recovery_receipt.json", receipt(plan, False))
        print(json.dumps({"status": "ready_for_manual_promotion_review", "promoted": False, "production_changed": False, "replay_verified": False}, indent=2))
        return 0
    if args.command == "replay":
        current = load(STATE)
        if current not in (final_state(plan, False), final_state(plan, True)):
            return fail("gate state does not match the evidence-bound recovery")
        receipt_path = ROOT / "work/recovery_receipt.json"
        try:
            current_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return fail("recovery receipt is missing or malformed")
        if current_receipt not in (receipt(plan, False), receipt(plan, True)):
            return fail("recovery receipt no longer matches the gate state")
        write_json(STATE, final_state(plan, True))
        write_json("work/recovery_receipt.json", receipt(plan, True))
        print(json.dumps({"status": "ready_for_manual_promotion_review", "replay_verified": True}, indent=2))
        return 0
    return fail("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
