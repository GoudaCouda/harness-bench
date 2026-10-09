#!/usr/bin/env python3
"""Offline controller for staging an access-review package.

The controller validates interface and provenance invariants only.  It does not
decide whether a proposed access change is correct and never changes an account.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".access_review_state.json"
RECEIPT = ROOT / "access_review_receipt.json"
PLAN_HEADER = [
    "change_id",
    "system",
    "action",
    "target_principal",
    "target_value",
    "idempotency_key",
    "approval_owner",
    "execution_state",
    "evidence_refs",
]
REVIEW_HEADER = [
    "system",
    "effective_entitlements",
    "review_status",
    "planned_change_ids",
    "owner",
    "conflict_state",
    "execution_state",
    "evidence_refs",
]
SOURCE_FILES = [
    "change_events.csv",
    "change_plan_template.csv",
    "direct_entitlements.csv",
    "employee_transfer.csv",
    "group_entitlements.csv",
    "group_graph.csv",
    "group_memberships.csv",
    "least_privilege_policy.md",
    "sod_policy.csv",
    "target_role_matrix.csv",
]
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z", re.ASCII)
ACTIONS = {"add_entitlement", "remove_entitlement", "remove_membership"}
REVIEW_STATUSES = {
    "change_planned",
    "compliant_no_change",
    "receipt_reconciled_no_change",
    "evidence_hold",
}
CONFLICT_STATES = {
    "none",
    "forbidden_nested_grant",
    "missing_required_entitlement",
    "sod_conflict",
    "exclusive_slot_conflict",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: digest(ROOT / name) for name in SOURCE_FILES}


def bundle_digest(hashes: dict[str, str]) -> str:
    payload = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path.name}: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name} must contain a JSON object")
    return value


def read_csv(path: Path, header: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"cannot parse {path.name}: {type(exc).__name__}") from exc
    if not rows or rows[0] != header:
        raise ValueError(f"{path.name}: exact header required")
    if any(len(row) != len(header) for row in rows[1:]):
        raise ValueError(f"{path.name}: every row must have {len(header)} cells")
    return [dict(zip(header, row)) for row in rows[1:]]


def target_systems() -> set[str]:
    with (ROOT / "target_role_matrix.csv").open(encoding="utf-8", newline="") as h:
        return {row["system"] for row in csv.DictReader(h)}


def validate_package(plan_path: Path, review_path: Path) -> dict:
    errors: list[str] = []
    try:
        plan = read_csv(plan_path, PLAN_HEADER)
    except ValueError as exc:
        errors.append(str(exc))
        plan = []
    try:
        review = read_csv(review_path, REVIEW_HEADER)
    except ValueError as exc:
        errors.append(str(exc))
        review = []

    ids = [row["change_id"] for row in plan]
    if any(not IDENTIFIER.fullmatch(value) for value in ids):
        errors.append("plan change_id values must use the published portable grammar")
    if len(ids) != len(set(ids)):
        errors.append("plan change_id values must be unique")
    semantic_keys = [(row["system"], row["action"], row["target_value"]) for row in plan]
    if len(semantic_keys) != len(set(semantic_keys)):
        errors.append("plan contains a duplicate semantic change")
    for number, row in enumerate(plan, start=2):
        if row["action"] not in ACTIONS:
            errors.append(f"plan row {number}: unsupported action")
        expected_key = (
            f"TR-200:{row['system']}:{row['target_value']}:{row['action']}:v1"
        )
        if row["idempotency_key"] != expected_key:
            errors.append(f"plan row {number}: idempotency key does not match payload")
        if row["target_principal"] != "E-200":
            errors.append(f"plan row {number}: target_principal must be E-200")
        if row["execution_state"] != "proposed_only":
            errors.append(f"plan row {number}: execution_state must be proposed_only")

    systems = [row["system"] for row in review]
    if len(systems) != len(set(systems)) or set(systems) != target_systems():
        errors.append("review must contain each target-role system exactly once")
    plan_ids = set(ids)
    referenced: list[str] = []
    for number, row in enumerate(review, start=2):
        if row["review_status"] not in REVIEW_STATUSES:
            errors.append(f"review row {number}: unsupported review_status")
        if row["conflict_state"] not in CONFLICT_STATES:
            errors.append(f"review row {number}: unsupported conflict_state")
        if row["execution_state"] != "proposed_only":
            errors.append(f"review row {number}: execution_state must be proposed_only")
        values = [] if row["planned_change_ids"] == "-" else row["planned_change_ids"].split("|")
        if any(not value or value not in plan_ids for value in values):
            errors.append(f"review row {number}: unresolved planned_change_ids")
        if len(values) != len(set(values)):
            errors.append(f"review row {number}: duplicate planned_change_ids")
        if (row["review_status"] == "change_planned") != bool(values):
            errors.append(f"review row {number}: status/change reference mismatch")
        referenced.extend(values)
    if sorted(referenced) != sorted(ids):
        errors.append("every plan change must be referenced exactly once by its system review")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "plan_rows": len(plan),
        "review_rows": len(review),
    }


def inspect_system(system: str) -> dict:
    if system not in target_systems():
        raise SystemExit(f"unknown target-role system: {system}")
    result: dict[str, object] = {"system": system}
    csv_sources = {
        "target_role_matrix.csv": "system",
        "direct_entitlements.csv": "system",
        "group_memberships.csv": "system",
        "group_graph.csv": "system",
        "group_entitlements.csv": "system",
        "change_events.csv": "system",
    }
    for name, field in csv_sources.items():
        with (ROOT / name).open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row.get(field) == system]
        result[name] = rows
    with (ROOT / "sod_policy.csv").open(encoding="utf-8", newline="") as handle:
        result["sod_policy.csv"] = [
            row
            for row in csv.DictReader(handle)
            if row.get("left_system") == system or row.get("right_system") == system
        ]
    return result


def stage_token(input_bundle: str, plan_sha: str, review_sha: str) -> str:
    payload = f"TR-200\n{input_bundle}\n{plan_sha}\n{review_sha}\nproposed_only\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def expected_receipt(state: dict) -> dict:
    return {
        "receipt_type": "local_access_review_stage",
        "transfer_id": "TR-200",
        "state_revision": state["revision"],
        "phase": "staged_for_approval",
        "input_bundle_sha256": state["input_bundle_sha256"],
        "plan_sha256": state["plan_sha256"],
        "review_sha256": state["review_sha256"],
        "stage_token": state["stage_token"],
        "execution_state": "proposed_only",
        "external_actions_executed": False,
    }


def command_status(_: argparse.Namespace) -> int:
    state = read_json(STATE)
    current = bundle_digest(source_hashes())
    print(json.dumps({**state, "sources_intact": current == state.get("input_bundle_sha256")}, indent=2, sort_keys=True))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    print(json.dumps(inspect_system(args.system), indent=2, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    result = validate_package(ROOT / args.plan, ROOT / args.review)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def command_stage(args: argparse.Namespace) -> int:
    plan = ROOT / args.plan
    review = ROOT / args.review
    result = validate_package(plan, review)
    if result["status"] != "pass":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    state = read_json(STATE)
    input_bundle = bundle_digest(source_hashes())
    if input_bundle != state.get("input_bundle_sha256"):
        raise SystemExit("immutable source bundle no longer matches controller state")
    plan_sha, review_sha = digest(plan), digest(review)
    token = stage_token(input_bundle, plan_sha, review_sha)
    already_staged = (
        state.get("phase") == "staged_for_approval"
        and state.get("stage_token") == token
    )
    if not already_staged:
        state = {
            "schema_version": 1,
            "transfer_id": "TR-200",
            "phase": "staged_for_approval",
            "revision": int(state.get("revision", 0)) + 1,
            "input_bundle_sha256": input_bundle,
            "plan_sha256": plan_sha,
            "review_sha256": review_sha,
            "stage_token": token,
            "execution_state": "proposed_only",
            "external_actions_executed": False,
        }
        STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        RECEIPT.write_text(json.dumps(expected_receipt(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "staged", "idempotent_replay": already_staged, "stage_token": token}, indent=2, sort_keys=True))
    return 0


def command_replay(_: argparse.Namespace) -> int:
    state = read_json(STATE)
    if state.get("phase") != "staged_for_approval" or not RECEIPT.is_file():
        print(json.dumps({"status": "fail", "errors": ["package has not been staged"]}, indent=2))
        return 2
    errors: list[str] = []
    current_bundle = bundle_digest(source_hashes())
    if current_bundle != state.get("input_bundle_sha256"):
        errors.append("source bundle hash mismatch")
    for filename, field in (("access_change_plan.csv", "plan_sha256"), ("access_review.csv", "review_sha256")):
        path = ROOT / filename
        if not path.is_file() or digest(path) != state.get(field):
            errors.append(f"{filename} hash mismatch")
    if state.get("stage_token") != stage_token(current_bundle, state.get("plan_sha256", ""), state.get("review_sha256", "")):
        errors.append("stage token mismatch")
    if read_json(RECEIPT) != expected_receipt(state):
        errors.append("stage receipt mismatch")
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "stage_token": state.get("stage_token")}, indent=2, sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Local planning-only access review controller")
    sub = parser.add_subparsers(required=True)
    status = sub.add_parser("status", help="show durable review state and input integrity")
    status.set_defaults(func=command_status)
    inspect = sub.add_parser("inspect", help="show raw local evidence for one system")
    inspect.add_argument("--system", required=True)
    inspect.set_defaults(func=command_inspect)
    validate = sub.add_parser("validate", help="validate package interfaces without deciding business correctness")
    validate.add_argument("--plan", default="access_change_plan.csv")
    validate.add_argument("--review", default="access_review.csv")
    validate.set_defaults(func=command_validate)
    stage = sub.add_parser("stage", help="stage a structurally valid local package for approval")
    stage.add_argument("--plan", default="access_change_plan.csv")
    stage.add_argument("--review", default="access_review.csv")
    stage.set_defaults(func=command_stage)
    replay = sub.add_parser("replay", help="verify staged hashes and deterministic receipt")
    replay.set_defaults(func=command_replay)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
