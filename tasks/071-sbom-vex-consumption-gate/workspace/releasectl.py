#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from risklib import (
    ROOT,
    blockers,
    canonical_sha,
    input_digests,
    load,
    normalized_ledger,
    normalized_rejections,
    validate_candidates,
    write_json,
)


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def paths(args: argparse.Namespace) -> tuple[Path, Path]:
    ledger = (ROOT / args.ledger).resolve()
    rejections = (ROOT / args.rejections).resolve()
    if not ledger.is_relative_to(ROOT) or not rejections.is_relative_to(ROOT):
        raise ValueError("candidate paths must stay inside the workspace")
    return ledger, rejections


def evaluated(args: argparse.Namespace) -> tuple[dict, dict, list[str]]:
    ledger_path, rejection_path = paths(args)
    ledger = read_object(ledger_path)
    rejections = read_object(rejection_path)
    return ledger, rejections, validate_candidates(ledger, rejections)


def expected_gate(ledger: dict) -> dict:
    policy = load("policy/release_policy.json")
    blocked = blockers(ledger)
    return {
        "release_id": ledger["release_id"],
        "state": policy["blocked_state"] if blocked else policy["clear_state"],
        "policy_version": policy["policy_version"],
        "blockers": blocked,
        "decision_ledger_sha256": canonical_sha(normalized_ledger(ledger)),
        "updated_by": "releasectl/1",
    }


def expected_receipt(ledger: dict, rejections: dict, replay_verified: bool) -> dict:
    gate = expected_gate(ledger)
    receipt = {
        "tool": "releasectl/1",
        "release_id": ledger["release_id"],
        "policy_version": ledger["policy_version"],
        "status": "pass",
        "gate_state": gate["state"],
        "blockers": gate["blockers"],
        "input_sha256": input_digests(),
        "decision_ledger_sha256": canonical_sha(normalized_ledger(ledger)),
        "rejections_sha256": canonical_sha(normalized_rejections(rejections)),
        "replay_verified": replay_verified,
    }
    if replay_verified:
        receipt["replay_fingerprint"] = canonical_sha(
            {
                "gate": gate,
                "ledger": normalized_ledger(ledger),
                "rejections": normalized_rejections(rejections),
                "inputs": receipt["input_sha256"],
            }
        )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate and transition the local release security gate")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("evaluate", "apply", "replay"):
        child = sub.add_parser(command)
        child.add_argument("--ledger", required=True)
        child.add_argument("--rejections", required=True)
    args = parser.parse_args()
    try:
        ledger, rejections, errors = evaluated(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "errors": [str(exc)]}, indent=2))
        return 2
    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, indent=2))
        return 2
    gate = expected_gate(ledger)
    if args.command == "evaluate":
        print(json.dumps({"status": "pass", "next_state": gate["state"], "blockers": gate["blockers"]}, indent=2))
        return 0
    gate_path = ROOT / "state/release_gate.json"
    receipt_path = ROOT / "work/evaluation_receipt.json"
    if args.command == "apply":
        current = read_object(gate_path)
        policy = load("policy/release_policy.json")
        if current.get("release_id") != ledger.get("release_id") or current.get("state") not in policy["allowed_initial_states"]:
            print(json.dumps({"status": "fail", "errors": ["gate is not in an allowed transition state"]}, indent=2))
            return 2
        write_json(gate_path, gate)
        write_json(receipt_path, expected_receipt(ledger, rejections, False))
        print(json.dumps({"status": "pass", "state": gate["state"], "receipt": "work/evaluation_receipt.json"}, indent=2))
        return 0
    if read_object(gate_path) != gate:
        print(json.dumps({"status": "fail", "errors": ["current gate does not match the derived transition"]}, indent=2))
        return 2
    write_json(receipt_path, expected_receipt(ledger, rejections, True))
    print(json.dumps({"status": "pass", "state": gate["state"], "replay_verified": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
