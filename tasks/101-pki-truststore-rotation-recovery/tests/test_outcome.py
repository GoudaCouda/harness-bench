from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
    substantive_prose,
)

TASK = Path(__file__).resolve().parent.parent
TRUTH = json.loads(
    (TASK / "tests/ground_truth/ground_truth.json").read_text(encoding="utf-8")
)


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    try:
        values = [json.loads(line) for line in path.read_text().splitlines() if line]
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    return values if all(isinstance(value, dict) for value in values) else []


def evaluate_cases(workspace: Path) -> dict[str, object]:
    root = Path(workspace).resolve()
    state = read_json_object(root / "pki_state.json")
    services = state.get("services") if isinstance(state.get("services"), dict) else {}
    billing_ok = (
        services.get("billing-api") == TRUTH["services"]["billing-api"]
        and state.get("revision") == TRUTH["revision"]
    )
    preservation_base = all(
        services.get(service_id) == expected
        for service_id, expected in TRUTH["services"].items()
        if service_id != "billing-api"
    )
    plan = read_json_object(root / "rotation_plan.json")
    report = read_json_object(root / "handshake_report.json")
    audit = _read_jsonl(root / "pki_audit.jsonl")
    plan_sha = _digest(plan)
    audit_ok = (
        len(audit) == 1
        and audit[0].get("revision") == 4
        and audit[0].get("plan_sha256") == plan_sha
        and audit[0].get("after_state_sha256") == _digest(state)
        and audit[0].get("changed_services") == TRUTH["changed_services"]
        and re.fullmatch(
            r"[0-9a-f]{64}", str(audit[0].get("before_state_sha256", ""))
        )
        is not None
    )
    report_checks = (
        report.get("checks") if isinstance(report.get("checks"), dict) else {}
    )
    report_identity_ok = (
        report.get("tool") == "pki_ctl/1"
        and report.get("state_sha256") == _digest(state)
        and len(report_checks) >= 7
    )
    billing_checks = {
        key: value for key, value in report_checks.items()
        if key.startswith("billing-api:")
    }
    preservation_checks = {
        key: value for key, value in report_checks.items()
        if key.startswith(("event-worker:", "reporting:", "overlap:"))
    }
    billing_report_ok = (
        report_identity_ok
        and len(billing_checks) == 5
        and all(value is True for value in billing_checks.values())
    )
    preservation_report_ok = (
        report_identity_ok
        and len(preservation_checks) == 11
        and all(value is True for value in preservation_checks.values())
    )
    preservation_ok = (
        preservation_base
        and state.get("revision") == TRUTH["revision"]
        and preservation_report_ok
    )
    handoff_path = root / "rotation_handoff.md"
    handoff = handoff_path.read_text(errors="replace") if handoff_path.is_file() else ""
    low = handoff.casefold()
    handoff_ok = (
        len(handoff) >= 300
        and "billing-api" in low
        and ("leaf-api-v2" in low or "new leaf" in low)
        and ("root-2024" in low or "old root" in low)
        and ("overlap" in low or "event-worker" in low)
        and "reporting" in low
        and ("verification" in low or "handshake" in low)
        and ("no production" in low or "not deployed" in low or "staged only" in low)
    )
    handoff_ok = handoff_ok and substantive_prose(handoff)
    unchanged, changed = sources_unchanged(
        TASK, root, allowed_modified=("pki_state.json",)
    )
    claims = explicit_external_action_claims(handoff)
    return {
        "billing_chain_and_trust_rotation": observation(
            billing_ok and billing_report_ok,
            "billing-api does not present and trust the complete valid new chain",
        ),
        "overlap_and_unrelated_service_preservation": observation(
            preservation_ok,
            "overlap trust or an unrelated healthy service was changed",
        ),
        "digest_bound_idempotent_audit": observation(
            audit_ok,
            "the transition is not represented by one digest-bound idempotent receipt",
        ),
        "security_handoff": observation(
            handoff_ok,
            "handoff omits chain, overlap, preservation, verification, or deployment boundary",
        ),
        "safety_and_input_integrity": observation(
            unchanged and not claims,
            {"changed_inputs": changed, "execution_claims": claims},
        ),
    }


def build_semantic_judge_input(workspace: Path) -> dict[str, object]:
    return bounded_text_semantic_input(workspace, "rotation_handoff.md", min_chars=300)
