#!/usr/bin/env python3
"""Offline AP supplier-bank release-gate controller.

The controller validates a submitted candidate package against visible local
records.  It never emits or exports a completed decision plan.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATE = ROOT / "release_gate_state.json"
PREVIEW = ROOT / ".release_gate_preview.json"
VERIFY = ROOT / "release_gate_verification.json"
RECEIPT = ROOT / "release_gate_receipt.json"
HANDOFF = ROOT / "controller_handoff.md"
HASH_MANIFEST = ROOT / "SOURCE_HASHES.json"
SOURCE_FILES = (
    "approval_events.csv",
    "bank_change_requests.csv",
    "batch_context.json",
    "callback_events.csv",
    "payment_queue.csv",
    "release_gate_policy.md",
    "suppliers.csv",
)
PLAN_FIELDS = {
    "schema_version",
    "batch_id",
    "policy_id",
    "source_checkpoint",
    "execution_mode",
    "external_actions_executed",
    "decisions",
}
ACTION_FIELDS = {"payment_id", "disposition", "reason_code", "evidence_refs"}
DISPOSITIONS = {"quarantine", "defer", "release_ready"}
REASON_CODES = {
    "supplier_inactive",
    "bank_mismatch",
    "invalid_change_chain",
    "beneficiary_unverified",
    "missing_dual_approval",
    "controls_satisfied",
}
HEADERS = {
    "payment_queue.csv": [
        "payment_id",
        "supplier_id",
        "invoice_id",
        "amount_usd",
        "payee_bank_token",
        "requested_at",
        "request_note",
    ],
    "suppliers.csv": [
        "supplier_id",
        "status",
        "master_bank_token",
        "prior_successful_payments",
        "beneficiary_verified_at",
    ],
    "bank_change_requests.csv": [
        "change_id",
        "supplier_id",
        "old_bank_token",
        "new_bank_token",
        "requested_at",
        "status",
    ],
    "callback_events.csv": [
        "callback_id",
        "change_id",
        "occurred_at",
        "contact_source",
        "result",
        "beneficiary_name_match",
    ],
    "approval_events.csv": [
        "approval_id",
        "subject_type",
        "subject_id",
        "role",
        "decision",
        "occurred_at",
    ],
}
LOCATOR_FILE = {
    "payment_queue.csv": "payment_id",
    "suppliers.csv": "supplier_id",
    "bank_change_requests.csv": "change_id",
    "callback_events.csv": "callback_id",
    "approval_events.csv": "approval_id",
}


class CandidateError(ValueError):
    """A bounded candidate or visible-source parse error."""


def _reject_constant(value: str) -> None:
    raise CandidateError(f"non-standard JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, *, max_bytes: int = 128_000) -> Any:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise CandidateError(f"{path.name}: missing, linked, or too large")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CandidateError(f"{path.name}: invalid JSON ({type(exc).__name__})") from exc


def _write_json(path: Path, value: object) -> None:
    if path.is_symlink():
        raise CandidateError(f"refusing linked output: {path.name}")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _read_rows(name: str) -> list[dict[str, str]]:
    path = ROOT / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 128_000:
        raise CandidateError(f"{name}: missing, linked, or too large")
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            raw = list(csv.reader(handle, strict=True))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CandidateError(f"{name}: invalid CSV ({type(exc).__name__})") from exc
    header = HEADERS[name]
    if not raw or raw[0] != header or any(len(row) != len(header) for row in raw[1:]):
        raise CandidateError(f"{name}: exact rectangular schema required")
    return [dict(zip(header, row)) for row in raw[1:]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    return {
        name: _sha256(ROOT / name)
        if (ROOT / name).is_file() and not (ROOT / name).is_symlink()
        else ""
        for name in SOURCE_FILES
    }


def _checkpoint(hashes: dict[str, str]) -> str:
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _source_checkpoint() -> str:
    manifest = _read_json(HASH_MANIFEST)
    if not isinstance(manifest, dict) or manifest != _source_hashes():
        raise CandidateError("immutable source bundle does not match SOURCE_HASHES.json")
    return _checkpoint(manifest)


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CandidateError(f"invalid visible timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise CandidateError(f"visible timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def _unsafe_text(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 2048:
        return True
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return True
    return any(
        character not in "\n\r\t" and unicodedata.category(character) in {"Cc", "Cf"}
        for character in value
    )


def _data() -> dict[str, Any]:
    context = _read_json(ROOT / "batch_context.json")
    if not isinstance(context, dict):
        raise CandidateError("batch_context.json must be an object")
    return {
        "context": context,
        "payments": _read_rows("payment_queue.csv"),
        "suppliers": _read_rows("suppliers.csv"),
        "changes": _read_rows("bank_change_requests.csv"),
        "callbacks": _read_rows("callback_events.csv"),
        "approvals": _read_rows("approval_events.csv"),
    }


def _indexes(data: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    return {
        "payments": {row["payment_id"]: row for row in data["payments"]},
        "suppliers": {row["supplier_id"]: row for row in data["suppliers"]},
        "changes": {row["change_id"]: row for row in data["changes"]},
        "callbacks": {row["callback_id"]: row for row in data["callbacks"]},
        "approvals": {row["approval_id"]: row for row in data["approvals"]},
    }


def _related(payment: dict[str, str], data: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    changes = [
        row for row in data["changes"] if row["supplier_id"] == payment["supplier_id"]
    ]
    change_ids = {row["change_id"] for row in changes}
    callbacks = [row for row in data["callbacks"] if row["change_id"] in change_ids]
    approvals = [
        row
        for row in data["approvals"]
        if (row["subject_type"] == "bank_change" and row["subject_id"] in change_ids)
        or (row["subject_type"] == "payment" and row["subject_id"] == payment["payment_id"])
    ]
    return {"changes": changes, "callbacks": callbacks, "approvals": approvals}


def _record_locators(payment: dict[str, str], data: dict[str, Any]) -> set[str]:
    related = _related(payment, data)
    locators = {
        f"payment_queue.csv#{payment['payment_id']}",
        f"suppliers.csv#{payment['supplier_id']}",
    }
    for group, filename, key in (
        (related["changes"], "bank_change_requests.csv", "change_id"),
        (related["callbacks"], "callback_events.csv", "callback_id"),
        (related["approvals"], "approval_events.csv", "approval_id"),
    ):
        locators.update(f"{filename}#{row[key]}" for row in group)
    return locators


def _recent_master_change(
    payment: dict[str, str], supplier: dict[str, str], data: dict[str, Any]
) -> dict[str, str] | None:
    cutoff = _time(str(data["context"]["cutoff_at"]))
    start = cutoff - timedelta(days=int(data["context"]["recent_change_days"]))
    matches = [
        row
        for row in data["changes"]
        if row["supplier_id"] == supplier["supplier_id"]
        and row["new_bank_token"] == supplier["master_bank_token"]
        and start <= _time(row["requested_at"]) <= cutoff
    ]
    return max(matches, key=lambda row: _time(row["requested_at"]), default=None)


def _change_chain_valid(change: dict[str, str], data: dict[str, Any]) -> bool:
    cutoff = _time(str(data["context"]["cutoff_at"]))
    requested = _time(change["requested_at"])
    callbacks = [row for row in data["callbacks"] if row["change_id"] == change["change_id"]]
    valid_callbacks = [
        row
        for row in callbacks
        if _time(row["occurred_at"]) > requested
        and row["contact_source"] == "independent_master_record"
        and row["result"] == "verified"
        and row["beneficiary_name_match"] == "yes"
        and _time(row["occurred_at"]) <= cutoff
    ]
    if change["status"] != "approved" or not valid_callbacks:
        return False
    callback_time = min(_time(row["occurred_at"]) for row in valid_callbacks)
    approvals = [
        row
        for row in data["approvals"]
        if row["subject_type"] == "bank_change"
        and row["subject_id"] == change["change_id"]
        and row["decision"] == "approved"
        and callback_time < _time(row["occurred_at"]) <= cutoff
    ]
    return {row["role"] for row in approvals} >= {"treasury", "ap_manager"}


def _payment_dual_approval(payment_id: str, data: dict[str, Any]) -> bool:
    cutoff = _time(str(data["context"]["cutoff_at"]))
    approvals = [
        row
        for row in data["approvals"]
        if row["subject_type"] == "payment"
        and row["subject_id"] == payment_id
        and row["decision"] == "approved"
        and _time(row["occurred_at"]) <= cutoff
    ]
    return {row["role"] for row in approvals} >= {"finance_manager", "treasury"}


def _decision_satisfies_policy(
    action: dict[str, Any], payment: dict[str, str], supplier: dict[str, str], data: dict[str, Any]
) -> bool:
    submitted = (action.get("disposition"), action.get("reason_code"))
    if supplier["status"] != "active":
        return submitted == ("quarantine", "supplier_inactive")
    if payment["payee_bank_token"] != supplier["master_bank_token"]:
        return submitted == ("quarantine", "bank_mismatch")
    change = _recent_master_change(payment, supplier, data)
    if change is not None and not _change_chain_valid(change, data):
        return submitted == ("quarantine", "invalid_change_chain")
    if int(supplier["prior_successful_payments"]) == 0:
        verified = supplier["beneficiary_verified_at"]
        if not verified or _time(verified) >= _time(payment["requested_at"]):
            return submitted == ("defer", "beneficiary_unverified")
    try:
        amount = Decimal(payment["amount_usd"])
        threshold = Decimal(str(data["context"]["high_value_threshold_usd"]))
    except InvalidOperation as exc:
        raise CandidateError("invalid visible monetary amount") from exc
    if amount >= threshold and not _payment_dual_approval(payment["payment_id"], data):
        return submitted == ("defer", "missing_dual_approval")
    return submitted == ("release_ready", "controls_satisfied")


def _semantic_plan(plan: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for action in plan.get("decisions", []):
        if not isinstance(action, dict):
            continue
        actions.append(
            {
                "payment_id": action.get("payment_id"),
                "disposition": action.get("disposition"),
                "reason_code": action.get("reason_code"),
                "evidence_refs": sorted(set(action.get("evidence_refs", [])))
                if isinstance(action.get("evidence_refs"), list)
                else [],
            }
        )
    actions.sort(key=lambda row: str(row["payment_id"]))
    return {
        "schema_version": plan.get("schema_version"),
        "batch_id": plan.get("batch_id"),
        "policy_id": plan.get("policy_id"),
        "source_checkpoint": plan.get("source_checkpoint"),
        "execution_mode": plan.get("execution_mode"),
        "external_actions_executed": plan.get("external_actions_executed"),
        "decisions": actions,
    }


def _plan_digest(plan: dict[str, Any]) -> str:
    raw = json.dumps(_semantic_plan(plan), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _issue(
    payment_id: str | None, field: str, rule: str, constraint: str, **detail: object
) -> dict[str, object]:
    result: dict[str, object] = {
        "payment_id": payment_id,
        "field": field,
        "rule": rule,
        "constraint": constraint,
    }
    result.update(detail)
    return result


def _validate_candidate(plan: object, data: dict[str, Any], checkpoint: str) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if not isinstance(plan, dict):
        return [_issue(None, "plan", "schema", "one_json_object_required")]
    if set(plan) != PLAN_FIELDS:
        issues.append(
            _issue(None, "plan", "schema", "exact_top_level_fields_required", received_count=len(plan))
        )
    context = data["context"]
    top_checks = (
        ("schema_version", plan.get("schema_version") == 1),
        ("batch_id", plan.get("batch_id") == context.get("batch_id")),
        ("policy_id", plan.get("policy_id") == context.get("policy_id")),
        ("source_checkpoint", plan.get("source_checkpoint") == checkpoint),
        ("execution_mode", plan.get("execution_mode") == "review_only"),
        ("external_actions_executed", plan.get("external_actions_executed") is False),
    )
    for field, passed in top_checks:
        if not passed:
            issues.append(_issue(None, field, "batch_contract", "published_value_not_satisfied"))
    actions = plan.get("decisions")
    if not isinstance(actions, list):
        issues.append(_issue(None, "decisions", "schema", "array_required"))
        return issues
    payment_map = _indexes(data)["payments"]
    supplier_map = _indexes(data)["suppliers"]
    ids: list[str] = []
    for position, raw in enumerate(actions):
        if not isinstance(raw, dict):
            issues.append(_issue(None, f"decisions[{position}]", "schema", "object_required"))
            continue
        payment_id = raw.get("payment_id") if isinstance(raw.get("payment_id"), str) else None
        if set(raw) != ACTION_FIELDS:
            issues.append(_issue(payment_id, "decision", "schema", "exact_action_fields_required"))
        if payment_id is None or _unsafe_text(payment_id):
            issues.append(_issue(payment_id, "payment_id", "schema", "safe_nonempty_string_required"))
            continue
        ids.append(payment_id)
        payment = payment_map.get(payment_id)
        if payment is None:
            issues.append(_issue(payment_id, "payment_id", "coverage", "unknown_visible_record"))
            continue
        disposition = raw.get("disposition")
        reason = raw.get("reason_code")
        if disposition not in DISPOSITIONS:
            issues.append(_issue(payment_id, "disposition", "schema", "published_enum_required"))
        if reason not in REASON_CODES:
            issues.append(_issue(payment_id, "reason_code", "schema", "published_enum_required"))
        supplier = supplier_map[payment["supplier_id"]]
        if disposition in DISPOSITIONS and reason in REASON_CODES and not _decision_satisfies_policy(raw, payment, supplier, data):
            issues.append(_issue(payment_id, "decision", "policy_precedence", "submitted_pair_not_supported"))
        refs = raw.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(_unsafe_text(value) for value in refs):
            issues.append(_issue(payment_id, "evidence_refs", "lineage", "safe_nonempty_string_array_required"))
            continue
        if len(refs) != len(set(refs)):
            issues.append(_issue(payment_id, "evidence_refs", "lineage", "duplicate_locator"))
        related = _record_locators(payment, data)
        if set(refs) != related:
            issues.append(
                _issue(
                    payment_id,
                    "evidence_refs",
                    "lineage",
                    "related_visible_records_incomplete_or_unrelated",
                    received_count=len(set(refs)),
                    related_record_count=len(related),
                )
            )
    submitted = set(ids)
    visible = set(payment_map)
    if len(ids) != len(submitted) or submitted != visible:
        issues.append(
            _issue(
                None,
                "decisions",
                "coverage",
                "each_visible_payment_exactly_once",
                received_unique_count=len(submitted),
                visible_count=len(visible),
            )
        )
    return issues


def _load_plan(name: str) -> dict[str, Any]:
    path = ROOT / name
    if path.parent != ROOT or path.name != name:
        raise CandidateError("plan must be a workspace-root filename")
    value = _read_json(path)
    if not isinstance(value, dict):
        raise CandidateError("plan must contain one JSON object")
    return value


def _preview_record(plan: dict[str, Any], checkpoint: str, issues: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "batch_id": plan.get("batch_id"),
        "candidate_digest": _plan_digest(plan),
        "source_checkpoint": checkpoint,
        "status": "pass" if not issues else "fail",
        "decision_count": len(plan.get("decisions", [])) if isinstance(plan.get("decisions"), list) else 0,
        "issue_count": len(issues),
        "execution_mode": "review_only",
        "external_actions_executed": False,
    }


def _state_records_as_plan(state: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    context = data["context"]
    return {
        "schema_version": 1,
        "batch_id": context["batch_id"],
        "policy_id": context["policy_id"],
        "source_checkpoint": state.get("source_checkpoint"),
        "execution_mode": "review_only",
        "external_actions_executed": False,
        "decisions": state.get("review_records", []),
    }


def command_status(_: argparse.Namespace) -> int:
    state = _read_json(STATE)
    checkpoint = _source_checkpoint()
    print(
        json.dumps(
            {
                "batch_id": state.get("batch_id"),
                "phase": state.get("phase"),
                "revision": state.get("revision"),
                "source_checkpoint": checkpoint,
                "sources_intact": state.get("source_checkpoint") == checkpoint,
                "interrupted_attempt": state.get("interrupted_attempt"),
                "review_record_count": len(state.get("review_records", [])),
                "execution_mode": state.get("execution_mode"),
                "external_actions_executed": state.get("external_actions_executed"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_inspect(_: argparse.Namespace) -> int:
    data = _data()
    state = _read_json(STATE)
    print(
        json.dumps(
            {
                "context": data["context"],
                "payment_ids": [row["payment_id"] for row in data["payments"]],
                "payment_count": len(data["payments"]),
                "state_phase": state.get("phase"),
                "recovery_required": bool(
                    isinstance(state.get("interrupted_attempt"), dict)
                    and state["interrupted_attempt"].get("rollback_required") is True
                ),
                "source_checkpoint": _source_checkpoint(),
                "query_hint": "query --payment PAYMENT_ID returns the linked visible record graph without a disposition",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def command_query(args: argparse.Namespace) -> int:
    data = _data()
    indexes = _indexes(data)
    payment = indexes["payments"].get(args.payment)
    if payment is None:
        raise SystemExit(f"unknown payment: {args.payment}")
    related = _related(payment, data)
    result = {
        "payment": payment,
        "supplier": indexes["suppliers"][payment["supplier_id"]],
        "bank_changes": related["changes"],
        "callbacks": related["callbacks"],
        "approvals": related["approvals"],
        "visible_locator_count": len(_record_locators(payment, data)),
        "decision": None,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_preview(args: argparse.Namespace) -> int:
    plan = _load_plan(args.plan)
    data = _data()
    checkpoint = _source_checkpoint()
    issues = _validate_candidate(plan, data, checkpoint)
    record = _preview_record(plan, checkpoint, issues)
    _write_json(PREVIEW, record)
    print(json.dumps({**record, "issues": issues}, indent=2, sort_keys=True))
    return 0 if not issues else 2


def command_apply(args: argparse.Namespace) -> int:
    plan = _load_plan(args.plan)
    data = _data()
    checkpoint = _source_checkpoint()
    issues = _validate_candidate(plan, data, checkpoint)
    if issues:
        print(json.dumps({"status": "fail", "issues": issues}, indent=2, sort_keys=True))
        return 2
    digest = _plan_digest(plan)
    try:
        preview = _read_json(PREVIEW)
    except CandidateError:
        preview = {}
    if not isinstance(preview, dict) or preview != _preview_record(plan, checkpoint, []):
        print(json.dumps({"status": "fail", "constraint": "matching_pass_preview_required"}, indent=2))
        return 2
    state = _read_json(STATE)
    if not isinstance(state, dict):
        raise CandidateError("release_gate_state.json must be an object")
    if state.get("source_checkpoint") != checkpoint:
        raise CandidateError("state source checkpoint is stale")
    if state.get("phase") in {"review_applied", "verified", "staged_for_controller"}:
        if state.get("applied_plan_digest") == digest:
            print(json.dumps({"status": "applied", "idempotent_replay": True, "candidate_digest": digest}, indent=2, sort_keys=True))
            return 0
        print(json.dumps({"status": "conflict", "constraint": "different_plan_already_applied"}, indent=2))
        return 2
    interrupted = state.get("interrupted_attempt")
    if not isinstance(interrupted, dict) or interrupted.get("rollback_required") is not True or interrupted.get("committed_records") != 0:
        raise CandidateError("state is not a safely recoverable interrupted attempt")
    next_state = {
        "schema_version": 1,
        "batch_id": data["context"]["batch_id"],
        "phase": "review_applied",
        "revision": int(state.get("revision", 0)) + 1,
        "source_checkpoint": checkpoint,
        "applied_plan_digest": digest,
        "review_records": _semantic_plan(plan)["decisions"],
        "recovery": {
            "prior_phase": state.get("phase"),
            "rolled_back_prepared_records": interrupted.get("prepared_records"),
            "committed_records_before_recovery": interrupted.get("committed_records"),
            "status": "completed",
        },
        "execution_mode": "review_only",
        "external_actions_executed": False,
    }
    _write_json(STATE, next_state)
    print(json.dumps({"status": "applied", "idempotent_replay": False, "recovered_interrupted_attempt": True, "candidate_digest": digest}, indent=2, sort_keys=True))
    return 0


def _verification_for(state: dict[str, Any], data: dict[str, Any]) -> dict[str, object]:
    records = state.get("review_records", [])
    counts = {name: 0 for name in sorted(DISPOSITIONS)}
    for row in records if isinstance(records, list) else []:
        if isinstance(row, dict) and row.get("disposition") in counts:
            counts[str(row["disposition"])] += 1
    return {
        "schema_version": 1,
        "batch_id": data["context"]["batch_id"],
        "status": "pass",
        "source_checkpoint": state.get("source_checkpoint"),
        "candidate_digest": state.get("applied_plan_digest"),
        "decision_count": len(records) if isinstance(records, list) else 0,
        "disposition_counts": counts,
        "unique_payment_ids": len({row.get("payment_id") for row in records if isinstance(row, dict)}) == len(records),
        "interrupted_attempt_recovered": state.get("recovery", {}).get("status") == "completed" if isinstance(state.get("recovery"), dict) else False,
        "sources_intact": state.get("source_checkpoint") == _source_checkpoint(),
        "execution_mode": "review_only",
        "external_actions_executed": False,
    }


def command_verify(_: argparse.Namespace) -> int:
    state = _read_json(STATE)
    data = _data()
    checkpoint = _source_checkpoint()
    if not isinstance(state, dict) or state.get("phase") not in {"review_applied", "verified", "staged_for_controller"}:
        raise CandidateError("apply a passing plan before verify")
    plan = _state_records_as_plan(state, data)
    issues = _validate_candidate(plan, data, checkpoint)
    if issues or state.get("applied_plan_digest") != _plan_digest(plan):
        print(json.dumps({"status": "fail", "issues": issues, "constraint": "applied_state_not_valid"}, indent=2, sort_keys=True))
        return 2
    verification = _verification_for(state, data)
    _write_json(VERIFY, verification)
    print(json.dumps(verification, indent=2, sort_keys=True))
    return 0


def _handoff_ok(state: dict[str, Any]) -> bool:
    if HANDOFF.is_symlink() or not HANDOFF.is_file() or HANDOFF.stat().st_size > 64_000:
        return False
    try:
        text = HANDOFF.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    folded = re.sub(r"[_-]+", " ", text.casefold())
    ids = [
        str(row.get("payment_id"))
        for row in state.get("review_records", [])
        if isinstance(row, dict) and row.get("disposition") != "release_ready"
    ]
    external_pattern = re.compile(
        r"\b(?:payment|supplier|vendor|bank change|callback)\b.{0,35}"
        r"\b(?:was|were|has been|have been)\s+"
        r"(?:released|paid|approved|contacted|updated|executed)\b"
    )
    segments = re.split(r"[.!?;\n]+|\b(?:but|however|whereas)\b", folded)
    positive_external = any(
        external_pattern.search(segment)
        and not re.search(r"\b(?:no|not|never|without|none)\b", segment)
        for segment in segments
    )
    required = (
        "review only",
        "no external",
        "independent callback",
        "beneficiary verification",
        "dual approval",
        "reactivat",
    )
    return all(payment_id.casefold() in text.casefold() for payment_id in ids) and all(term in folded for term in required) and not positive_external


def _receipt_for(state: dict[str, Any]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_type": "local_ap_release_gate_stage",
        "batch_id": state["batch_id"],
        "phase": "staged_for_controller",
        "state_revision": state["revision"],
        "source_checkpoint": state["source_checkpoint"],
        "candidate_digest": state["applied_plan_digest"],
        "verification_sha256": _sha256(VERIFY),
        "handoff_sha256": _sha256(HANDOFF),
        "execution_mode": "review_only",
        "external_actions_executed": False,
    }


def command_stage(args: argparse.Namespace) -> int:
    plan = _load_plan(args.plan)
    data = _data()
    checkpoint = _source_checkpoint()
    issues = _validate_candidate(plan, data, checkpoint)
    state = _read_json(STATE)
    if issues or not isinstance(state, dict) or state.get("applied_plan_digest") != _plan_digest(plan):
        print(json.dumps({"status": "fail", "constraint": "applied_candidate_not_current", "issues": issues}, indent=2, sort_keys=True))
        return 2
    if _read_json(VERIFY) != _verification_for(state, data):
        raise CandidateError("verification is missing or stale")
    if not _handoff_ok(state):
        raise CandidateError("handoff is incomplete or claims an external action")
    if state.get("phase") == "staged_for_controller":
        expected_receipt = _receipt_for(state)
        if _read_json(RECEIPT) != expected_receipt:
            raise CandidateError("staged receipt is stale")
        print(json.dumps({"status": "staged", "idempotent_replay": True, "candidate_digest": state["applied_plan_digest"]}, indent=2, sort_keys=True))
        return 0
    if state.get("phase") != "review_applied":
        raise CandidateError("state must be review_applied before staging")
    staged = dict(state)
    staged["phase"] = "staged_for_controller"
    staged["revision"] = int(state["revision"]) + 1
    staged["verification_sha256"] = _sha256(VERIFY)
    staged["handoff_sha256"] = _sha256(HANDOFF)
    _write_json(STATE, staged)
    _write_json(RECEIPT, _receipt_for(staged))
    print(json.dumps({"status": "staged", "idempotent_replay": False, "candidate_digest": staged["applied_plan_digest"]}, indent=2, sort_keys=True))
    return 0


def command_replay(args: argparse.Namespace) -> int:
    before_state = STATE.read_bytes()
    before_receipt = RECEIPT.read_bytes() if RECEIPT.is_file() else b""
    plan = _load_plan(args.plan)
    data = _data()
    checkpoint = _source_checkpoint()
    issues = _validate_candidate(plan, data, checkpoint)
    state = _read_json(STATE)
    receipt = _read_json(RECEIPT)
    errors: list[str] = []
    if issues:
        errors.append("candidate no longer validates")
    if state.get("phase") != "staged_for_controller" or state.get("applied_plan_digest") != _plan_digest(plan):
        errors.append("candidate conflicts with staged state")
    if _read_json(VERIFY) != _verification_for(state, data):
        errors.append("verification is stale")
    if not _handoff_ok(state):
        errors.append("handoff is incomplete")
    if receipt != _receipt_for(state):
        errors.append("receipt is stale")
    byte_stable = STATE.read_bytes() == before_state and RECEIPT.read_bytes() == before_receipt
    if not byte_stable:
        errors.append("replay changed staged bytes")
    result = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "semantic_equivalent": not issues and state.get("applied_plan_digest") == _plan_digest(plan),
        "byte_stable": byte_stable,
        "external_actions_executed": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="offline AP supplier-bank release-gate controller")
    sub = parser.add_subparsers(required=True)
    sub.add_parser("status", help="show interrupted local state and source integrity").set_defaults(func=command_status)
    sub.add_parser("inspect", help="show batch identity, payment IDs, and recovery state").set_defaults(func=command_inspect)
    query = sub.add_parser("query", help="show the linked visible graph for one payment")
    query.add_argument("--payment", required=True)
    query.set_defaults(func=command_query)
    preview = sub.add_parser("preview", help="validate a candidate without changing review state")
    preview.add_argument("plan")
    preview.set_defaults(func=command_preview)
    apply = sub.add_parser("apply", help="atomically recover and apply a passing preview")
    apply.add_argument("plan")
    apply.set_defaults(func=command_apply)
    sub.add_parser("verify", help="independently verify the applied local review state").set_defaults(func=command_verify)
    stage = sub.add_parser("stage", help="stage a verified review package for controller review")
    stage.add_argument("plan")
    stage.set_defaults(func=command_stage)
    replay = sub.add_parser("replay", help="check semantic replay and staged-byte stability")
    replay.add_argument("plan")
    replay.set_defaults(func=command_replay)
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except CandidateError as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
