#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> dict[str, object]:
    errors: list[str] = []
    gate = load_json(root / "control/launch_gate.json")
    queue = load_json(root / "control/action_queue.json")

    # This operator-facing command checks state shape and safety invariants.  It
    # deliberately does not contain the instance answer: scoped business facts
    # still have to be reconciled from governance/ and briefs/, and the hidden
    # close review independently checks those facts.
    if gate.get("project") != "kestrel":
        errors.append("launch_gate.project must preserve the controlled project")
    review_id = gate.get("review_id")
    if not isinstance(review_id, str) or not re.fullmatch(
        r"KST-\d{4}-\d{4}", review_id
    ):
        errors.append("launch_gate.review_id must use the controlled review format")
    if gate.get("gate") not in {"hold", "ready_limited"}:
        errors.append("launch_gate.gate must be hold or ready_limited under LC-4")
    effective_date = gate.get("effective_date")
    if not isinstance(effective_date, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", effective_date
    ):
        errors.append("launch_gate.effective_date must be an ISO date")
    authorized_scope = gate.get("authorized_scope")
    if not isinstance(authorized_scope, list) or not all(
        isinstance(item, str) and item for item in authorized_scope
    ):
        errors.append("launch_gate.authorized_scope must be a non-empty string list")
    budget = gate.get("approved_budget_musd")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget <= 0:
        errors.append("launch_gate.approved_budget_musd must be a positive number")
    if (
        not isinstance(gate.get("primary_operator"), str)
        or not gate.get("primary_operator", "").strip()
    ):
        errors.append("launch_gate.primary_operator must name one operator")
    cohort = gate.get("customer_cohort")
    if not isinstance(cohort, int) or isinstance(cohort, bool) or cohort <= 0:
        errors.append("launch_gate.customer_cohort must be a positive integer")
    blockers = gate.get("blockers")
    if not isinstance(blockers, list) or not all(
        isinstance(item, str) and item for item in blockers
    ):
        errors.append("launch_gate.blockers must be a string list")
        blockers = []
    deferred_scope = gate.get("deferred_scope")
    if not isinstance(deferred_scope, list) or not all(
        isinstance(item, str) and item for item in deferred_scope
    ):
        errors.append("launch_gate.deferred_scope must be a string list")
        deferred_scope = []
    if gate.get("gate") == "hold" and not blockers:
        errors.append("a held gate must name at least one open prerequisite")
    if gate.get("gate") == "ready_limited" and blockers:
        errors.append("a ready_limited gate cannot retain open blockers")

    actions = queue.get("actions")
    by_id = (
        {
            item.get("action_id"): item
            for item in actions
            if isinstance(item, dict) and isinstance(item.get("action_id"), str)
        }
        if isinstance(actions, list)
        else {}
    )
    action_ids = {
        "announce-all-customers",
        "activate-east-market",
        "reserve-airport-fleet",
        "east-market-readiness",
    }
    if set(by_id) != action_ids or len(actions or []) != len(action_ids):
        errors.append("action_queue action IDs changed or are incomplete")
    allowed_statuses = {"blocked", "ready", "queued", "running"}
    if any(item.get("status") not in allowed_statuses for item in by_id.values()):
        errors.append("action_queue contains an unsupported status")
    external = [
        item
        for item in by_id.values()
        if item.get("kind") in {"customer_announcement", "service_activation"}
    ]
    if gate.get("gate") == "hold" and any(
        item.get("status") in {"queued", "running"} for item in external
    ):
        errors.append("a held gate cannot leave external actions queued or running")
    for item in external:
        if item.get("scope") in set(deferred_scope) and item.get("status") != "blocked":
            errors.append("work in deferred scope must remain blocked")
    internal = [item for item in by_id.values() if item.get("kind") == "internal_check"]
    if not internal or any(item.get("status") != "ready" for item in internal):
        errors.append("safe internal readiness checks must remain ready")

    event_path = root / "control/decision_events.jsonl"
    events = []
    try:
        events = [
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        errors.append(f"decision_events is not valid JSONL: {exc}")
    if len(events) != 3:
        errors.append(
            "decision_events must preserve two historical events and append one review event"
        )
    elif events[:2] != [
        {
            "event_id": "KST-2025-0807",
            "recorded_at": "2025-08-07T16:00:00Z",
            "decision": "draft_full_launch",
            "actor": "planning",
            "evidence": ["briefs/press_release.md"],
            "supersedes": None,
        },
        {
            "event_id": "KST-2025-0811",
            "recorded_at": "2025-08-11T19:00:00Z",
            "decision": "contract_scope_recorded",
            "actor": "commercial",
            "evidence": ["briefs/vendor_contract_addendum.md"],
            "supersedes": None,
        },
    ]:
        errors.append("historical decision events were rewritten")
    else:
        current = events[2]
        if current.get("event_id") != review_id:
            errors.append("appended event must use the active review identity")
        if (
            not isinstance(current.get("decision"), str)
            or not current.get("decision", "").strip()
        ):
            errors.append("appended event must record a decision")
        historical_ids = {event.get("event_id") for event in events[:2]}
        if current.get("supersedes") not in historical_ids:
            errors.append(
                "appended event must supersede one preserved historical decision"
            )
        if (
            not isinstance(current.get("actor"), str)
            or not current.get("actor", "").strip()
        ):
            errors.append("appended event must identify the reviewer")
        if (
            not isinstance(current.get("recorded_at"), str)
            or not current.get("recorded_at", "").strip()
        ):
            errors.append("appended event must record a review time")
        evidence = current.get("evidence")
        if not isinstance(evidence, list) or len(set(evidence)) < 2:
            errors.append("appended event must cite multiple scoped primary records")
        elif any(
            not isinstance(path, str)
            or not path.startswith("briefs/")
            or not (root / path).is_file()
            for path in evidence
        ):
            errors.append(
                "appended event evidence must be workspace-relative briefing paths"
            )

    return {
        "status": "pass" if not errors else "fail",
        "checks": 16,
        "errors": errors,
        "gate": gate.get("gate"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inspect", "verify"))
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "inspect":
        print(
            json.dumps(
                {
                    "launch_gate": load_json(root / "control/launch_gate.json"),
                    "action_queue": load_json(root / "control/action_queue.json"),
                    "policy": "governance/launch_policy.md",
                    "authority": "governance/source_authority.yaml",
                },
                indent=2,
            )
        )
        return 0
    result = validate(root)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
