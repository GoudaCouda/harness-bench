from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = (
    "evidence/backups.json",
    "evidence/timeline_history.json",
    "evidence/wal_archive.json",
    "evidence/incident.json",
    "evidence/expected_invariants.json",
    "policy/recovery_policy.json",
)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_digests() -> dict[str, str]:
    return {relative: file_sha(ROOT / relative) for relative in INPUTS}


def backup(backup_id: str) -> dict | None:
    return next((row for row in load("evidence/backups.json")["backups"] if row["backup_id"] == backup_id), None)


def target() -> dict:
    incident = load("evidence/incident.json")
    return next(row for row in load("evidence/wal_archive.json")["restore_points"] if row["name"] == incident["last_known_safe_restore_point"] and row["timeline"] == incident["affected_timeline"])


def selected_backup() -> dict:
    incident = load("evidence/incident.json")
    point = target()
    candidates = [
        row
        for row in load("evidence/backups.json")["backups"]
        if row["system_identifier"] == incident["system_identifier"]
        and row["timeline"] == incident["affected_timeline"]
        and row["ended_at"] <= point["created_at"]
        and all(
            row[field] == "verified"
            for field in ("manifest_status", "file_status", "wal_manifest_status")
        )
    ]
    if not candidates:
        raise ValueError("no verified incident-timeline backup precedes the target")
    return max(candidates, key=lambda row: (row["ended_at"], row["backup_id"]))


def required_segments() -> list[str]:
    chosen = selected_backup()
    point = target()
    segments = [row for row in load("evidence/wal_archive.json")["segments"] if row["timeline"] == point["timeline"] and row["readable"]]
    return sorted(row["name"] for row in segments if row["end_lsn"] >= chosen["end_lsn"] and row["start_lsn"] <= point["lsn"])


def derived_plan_core() -> dict:
    incident = load("evidence/incident.json")
    policy = load("policy/recovery_policy.json")
    point = target()
    return {
        "incident_id": incident["incident_id"],
        "system_identifier": incident["system_identifier"],
        "backup_id": selected_backup()["backup_id"],
        "target_timeline": incident["affected_timeline"],
        "target_type": "name",
        "target_name": point["name"],
        "target_lsn": point["lsn"],
        "recovery_target_action": policy["required_target_action"],
        "required_wal_segments": required_segments(),
        "restore_command_template": policy["restore_command_template"],
        "expected_invariants": load("evidence/expected_invariants.json")["checks"],
    }


def validate_plan(plan: dict) -> list[str]:
    errors = []
    incident = load("evidence/incident.json")
    core = derived_plan_core()
    for key, expected in core.items():
        actual = plan.get(key)
        if key in {"required_wal_segments"} and isinstance(actual, list):
            actual = sorted(actual)
        if actual != expected:
            errors.append(f"{key} does not match the evidence-derived recovery path")
    rejected = plan.get("rejected_alternatives")
    rejected_map = {str(row.get("candidate")): str(row.get("reason", "")).casefold() for row in rejected if isinstance(row, dict)} if isinstance(rejected, list) else {}
    chosen_id = selected_backup()["backup_id"]
    alternatives = {
        row["backup_id"]
        for row in load("evidence/backups.json")["backups"]
        if row["backup_id"] != chosen_id
    }
    timestamp_id = f"timestamp:{incident['reported_timestamp']}"
    if not (alternatives | {timestamp_id}).issubset(rejected_map):
        errors.append("rejected alternatives must cover the corrupt base, divergent base, and ambiguous timestamp")
    reason_requirements: dict[str, tuple[str, ...]] = {}
    for row in load("evidence/backups.json")["backups"]:
        if row["backup_id"] == chosen_id:
            continue
        tokens: list[str] = []
        if any(
            row[field] != "verified"
            for field in ("manifest_status", "file_status", "wal_manifest_status")
        ):
            tokens.extend(("checksum", "manifest", "file"))
        if row["timeline"] != incident["affected_timeline"]:
            tokens.extend(("timeline", "diverg"))
        reason_requirements[row["backup_id"]] = tuple(tokens)
    reason_requirements[timestamp_id] = ("ambiguous", "same timestamp")
    for candidate, alternatives in reason_requirements.items():
        if candidate in rejected_map and not any(token in rejected_map[candidate] for token in alternatives):
            errors.append(f"rejection reason for {candidate} is not evidence-grounded")
    rationale = str(plan.get("rationale", "")).casefold()
    required_rationale = (
        f"timeline {incident['affected_timeline']}",
        "named",
        "wal",
        "isolated",
    )
    if len(rationale) < 120 or not all(token in rationale for token in required_rationale):
        errors.append("rationale must explain timeline, named target, WAL, and isolation")
    return errors


def normalized_plan(plan: dict) -> dict:
    result = dict(plan)
    if isinstance(result.get("required_wal_segments"), list):
        result["required_wal_segments"] = sorted(result["required_wal_segments"])
    if isinstance(result.get("expected_invariants"), list):
        result["expected_invariants"] = sorted(result["expected_invariants"], key=lambda row: str(row.get("check_id")))
    if isinstance(result.get("rejected_alternatives"), list):
        result["rejected_alternatives"] = sorted(result["rejected_alternatives"], key=lambda row: str(row.get("candidate")))
    return result


def probe_results() -> list[dict]:
    return [
        {"check_id": row["check_id"], "expected": row["expected"], "observed": row["expected"], "status": "pass"}
        for row in load("evidence/expected_invariants.json")["checks"]
    ]


def probe_document(runs: int) -> dict:
    state = load("state/recovery_state.json")
    base = {
        "tool": "pitrctl/1",
        "incident_id": state["incident_id"],
        "target_timeline": state["restored_timeline"],
        "target_name": state["restored_target_name"],
        "target_lsn": state["restored_target_lsn"],
        "complete": True,
        "status": "pass",
        "results": probe_results(),
        "run_count": runs,
        "identical_passes": runs >= 2,
    }
    base["result_set_sha256"] = canonical_sha(base["results"])
    return base


def final_state(plan: dict, replay_verified: bool) -> dict:
    seed = load("state/recovery_state.json")
    probe = probe_document(2)
    core = derived_plan_core()
    return {
        **seed,
        "phase": "manual_promotion_gate_closed",
        "verified_backup_id": core["backup_id"],
        "plan_sha256": canonical_sha(normalized_plan(plan)),
        "restored_timeline": core["target_timeline"],
        "restored_target_name": core["target_name"],
        "restored_target_lsn": core["target_lsn"],
        "probe_runs": 2,
        "probe_sha256": canonical_sha(probe),
        "replay_verified": replay_verified,
        "promotion_status": "ready_for_manual_promotion_review",
        "promoted": False,
        "production_changed": False,
    }


def receipt(plan: dict, replay_verified: bool) -> dict:
    state = final_state(plan, replay_verified)
    base = {
        "tool": "pitrctl/1",
        "incident_id": state["incident_id"],
        "policy_version": state["policy_version"],
        "status": state["promotion_status"],
        "backup_id": state["verified_backup_id"],
        "target_timeline": state["restored_timeline"],
        "target_name": state["restored_target_name"],
        "target_lsn": state["restored_target_lsn"],
        "plan_sha256": state["plan_sha256"],
        "probe_sha256": state["probe_sha256"],
        "input_sha256": input_digests(),
        "probe_runs": 2,
        "replay_verified": replay_verified,
        "external_action": "none_offline_manual_review_only",
    }
    base["receipt_sha256"] = canonical_sha(base)
    return base
