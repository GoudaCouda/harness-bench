#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/claims.db"
PLAN_FIELDS = {
    "schema_version",
    "recovery_id",
    "source_checkpoint",
    "decisions",
    "event_dispositions",
    "totals",
    "external_actions_executed",
}
DECISION_FIELDS = {
    "case_id",
    "tracking_number",
    "carrier",
    "survivor_case_id",
    "disposition",
    "final_state",
    "requested_amount_cents",
    "locally_allowed_amount_cents",
    "response_deadline",
    "next_local_action",
    "claim_line_ids",
    "evidence_refs",
}
EVENT_FIELDS = {
    "delivery_id",
    "event_id",
    "source_case_id",
    "effective_case_id",
    "carrier_sequence",
    "disposition",
}
TOTAL_FIELDS = {
    "active_requested_amount_cents",
    "ready_packet_amount_cents",
    "preserved_submitted_amount_cents",
    "preserved_paid_amount_cents",
}
CASE_MUTABLE = {
    "state",
    "approved_amount_cents",
    "survivor_case_id",
    "response_deadline",
    "version",
}
DECISION_VOCABULARY = {
    "disposition": [
        "awaiting_carrier",
        "closed_paid_preserved",
        "denial_response_due",
        "hold_invoice_identity_mismatch",
        "hold_missing_damage_evidence",
        "hold_missing_signed_bol",
        "merged_into_survivor",
        "ready_local_packet",
    ],
    "final_state": [
        "awaiting_carrier",
        "carrier_acknowledged",
        "closed_paid",
        "denial_response_due",
        "held",
        "merged",
        "ready_local_packet",
    ],
    "next_local_action": [
        "monitor_carrier_response",
        "none",
        "resolve_evidence_hold",
        "stage_denial_response_packet",
        "stage_local_claim_packet",
    ],
}
EVENT_DISPOSITION_VOCABULARY = [
    "applied",
    "applied_to_survivor",
    "closed_case_ignored",
    "duplicate_delivery_ignored",
    "unknown_case_ignored",
]
LOCATOR_GRAMMAR = {
    "case": "state/claims.db#cases:<case_id>",
    "claim_line": "state/claims.db#claim_lines:<line_id>",
    "evidence_blob": "evidence/blobs/<blob_id>.json#<blob_id>",
    "carrier_event": "evidence/carrier_events.jsonl#<event_id>",
    "settlement_policy": "policy/claims_policy.json#settlement_rules",
    "duplicate_policy": "policy/claims_policy.json#duplicate_survivor_rule",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain one JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def load_events() -> list[dict[str, Any]]:
    result = []
    try:
        lines = (ROOT / "evidence/carrier_events.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read carrier events: {exc}") from exc
    for number, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed carrier event delivery line {number}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"carrier event line {number} is not an object")
        result.append(item)
    return result


def source_manifest() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source_manifest.json is malformed")
    changed = []
    for locator, expected in files.items():
        try:
            actual = digest((ROOT / str(locator)).read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def baseline_state(connection: sqlite3.Connection, recovery_id: str) -> dict[str, Any]:
    cases = {row["case_id"]: row for row in rows(connection, "cases", "case_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
    journal = rows(connection, "recovery_journal", "journal_id")
    current = runs.get(recovery_id)
    if current and current["status"] in {"committed", "staged_local_bundle"}:
        for row in journal:
            if row["recovery_id"] == recovery_id:
                cases[row["case_id"]] = json.loads(row["before_json"])
    for row in journal:
        run = runs.get(row["recovery_id"])
        if run and run["status"] == "interrupted" and not row["restored"]:
            cases[row["case_id"]] = json.loads(row["before_json"])
    system = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
    return {
        "cases": [cases[key] for key in sorted(cases)],
        "claim_lines": rows(connection, "claim_lines", "line_id"),
        "evidence_blobs": rows(connection, "evidence_blobs", "blob_id"),
        "source_revision": int(system.get("source_revision", "0")),
    }


def protected_source_context(policy: dict[str, Any]) -> dict[str, Any]:
    """Return public source identity facts, never a completed claims plan."""
    manifest, source_bundle_hash = source_manifest()
    with sqlite3.connect(DB) as connection:
        baseline = baseline_state(connection, str(policy["recovery_id"]))
    checkpoint_payload = {
        "immutable_source_hashes": manifest["files"],
        "source_bundle_hash": source_bundle_hash,
        "source_revision": baseline["source_revision"],
        "baseline_cases": baseline["cases"],
        "claim_lines": baseline["claim_lines"],
        "evidence_blobs": baseline["evidence_blobs"],
    }
    return {
        "manifest": manifest,
        "source_bundle_hash": source_bundle_hash,
        "baseline": baseline,
        "source_checkpoint": digest(canonical(checkpoint_payload)),
    }


def survivor_map(cases: list[dict[str, Any]]) -> dict[str, str]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for case in cases:
        groups.setdefault((case["carrier"], case["tracking_number"]), []).append(case)
    result = {}
    for members in groups.values():
        survivor = min(members, key=lambda row: (row["opened_at"], row["case_id"]))["case_id"]
        for member in members:
            result[member["case_id"]] = survivor
    return result


def event_facts(
    deliveries: list[dict[str, Any]],
    cases: dict[str, dict[str, Any]],
    survivors: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], set[str]]:
    seen: set[str] = set()
    dispositions = []
    accepted: dict[str, list[dict[str, Any]]] = {}
    accepted_ids: set[str] = set()
    for delivery in deliveries:
        source = str(delivery.get("case_id", ""))
        event_id = str(delivery.get("event_id", ""))
        effective = survivors.get(source, source)
        if event_id in seen:
            status = "duplicate_delivery_ignored"
        else:
            seen.add(event_id)
            if source not in cases:
                status = "unknown_case_ignored"
            elif cases[effective]["state"] == "closed_paid":
                status = "closed_case_ignored"
            else:
                status = "applied_to_survivor" if effective != source else "applied"
                accepted.setdefault(effective, []).append(delivery)
                accepted_ids.add(event_id)
        dispositions.append(
            {
                "delivery_id": str(delivery.get("delivery_id")),
                "event_id": event_id,
                "source_case_id": source,
                "effective_case_id": effective,
                "carrier_sequence": int(delivery.get("carrier_sequence", -1)),
                "disposition": status,
            }
        )
    for case_events in accepted.values():
        case_events.sort(key=lambda item: (int(item["carrier_sequence"]), str(item["event_id"])))
    return dispositions, accepted, accepted_ids


def valid_evidence(
    blob: dict[str, Any], line: dict[str, Any], accepted_event_ids: set[str]
) -> bool:
    if blob["line_id"] != line["line_id"]:
        return False
    event_id = blob["received_via_event_id"]
    if event_id and event_id not in accepted_event_ids:
        return False
    try:
        hash_ok = digest((ROOT / blob["local_path"]).read_bytes()) == blob["sha256"]
    except OSError:
        hash_ok = False
    return hash_ok and blob["shipment_id"] == line["shipment_id"]


def _validate_candidate(candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    problems: list[str] = []
    if set(candidate) != PLAN_FIELDS:
        problems.append(
            f"top-level fields must be exactly {sorted(PLAN_FIELDS)}; "
            "query `python3 claimsctl.py contract --json`"
        )
    raw_decisions = candidate.get("decisions")
    if not isinstance(raw_decisions, list) or any(
        not isinstance(row, dict) or set(row) != DECISION_FIELDS
        for row in raw_decisions or []
    ):
        problems.append(
            f"every decision must have exactly {sorted(DECISION_FIELDS)}; "
            "query the public vocabulary and locator grammar with `claimsctl.py contract --json`"
        )
    raw_events = candidate.get("event_dispositions")
    if not isinstance(raw_events, list) or any(
        not isinstance(row, dict) or set(row) != EVENT_FIELDS
        for row in raw_events or []
    ):
        problems.append(
            f"every event disposition must have exactly {sorted(EVENT_FIELDS)}; "
            "query `claimsctl.py contract --json`"
        )
    if not isinstance(candidate.get("totals"), dict) or set(candidate.get("totals", {})) != TOTAL_FIELDS:
        problems.append(f"totals fields must be exactly {sorted(TOTAL_FIELDS)}")
    if candidate.get("external_actions_executed") is not False:
        problems.append("external_actions_executed must be false")
    normalized = normalized_plan(candidate)
    actual: dict[str, dict[str, Any]] = {}
    for row in normalized.get("decisions", []):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id", ""))
        if case_id in actual:
            problems.append(f"duplicate decision object: {case_id}")
        actual[case_id] = row

    policy = load_json(ROOT / "policy/claims_policy.json")
    context = protected_source_context(policy)
    deliveries = load_events()
    baseline = context["baseline"]
    cases = {row["case_id"]: row for row in baseline["cases"]}
    survivors = survivor_map(baseline["cases"])
    event_rows, accepted_events, accepted_ids = event_facts(deliveries, cases, survivors)
    member_ids: dict[str, list[str]] = {}
    for case_id, survivor in survivors.items():
        member_ids.setdefault(survivor, []).append(case_id)
    lines_by_case: dict[str, list[dict[str, Any]]] = {}
    for line in baseline["claim_lines"]:
        lines_by_case.setdefault(line["case_id"], []).append(line)
    blobs_by_line: dict[str, list[dict[str, Any]]] = {}
    for blob in baseline["evidence_blobs"]:
        blobs_by_line.setdefault(blob["line_id"], []).append(blob)

    expected_ids: set[str] = set()
    final_cases: dict[str, dict[str, Any]] = {}
    active_requested = 0
    ready_amount = 0
    submitted_amount = 0
    paid_amount = 0
    partial_rate = int(policy["damage_missing_packaging_percent"])
    for case_id in sorted(cases):
        original = cases[case_id]
        survivor = survivors[case_id]
        if survivor != case_id:
            decision = {
                "case_id": case_id,
                "tracking_number": original["tracking_number"],
                "carrier": original["carrier"],
                "survivor_case_id": survivor,
                "disposition": "merged_into_survivor",
                "final_state": "merged",
                "requested_amount_cents": 0,
                "locally_allowed_amount_cents": 0,
                "response_deadline": None,
                "next_local_action": "none",
                "claim_line_ids": [],
                "evidence_refs": sorted(
                    [
                        f"state/claims.db#cases:{case_id}",
                        "policy/claims_policy.json#duplicate_survivor_rule",
                    ]
                ),
            }
            final = dict(original)
            final.update(
                {
                    "state": "merged",
                    "approved_amount_cents": 0,
                    "survivor_case_id": survivor,
                    "response_deadline": None,
                    "version": int(original["version"]) + 1,
                }
            )
            expected_ids.add(case_id)
            candidate_row = actual.get(case_id)
            if candidate_row is not None:
                different = sorted(
                    key
                    for key in DECISION_FIELDS
                    if candidate_row.get(key) != decision[key]
                )
                if different:
                    problems.append(
                        f"decision {case_id} differs in fields: {', '.join(different)} "
                        "[evidence: duplicate rule and restored SQLite case]"
                    )
            final_cases[case_id] = final
            continue

        effective_lines = []
        for member in member_ids[survivor]:
            effective_lines.extend(lines_by_case.get(member, []))
        effective_lines.sort(key=lambda row: row["line_id"])
        requested = sum(int(row["requested_amount_cents"]) for row in effective_lines)
        evidence_refs = {f"state/claims.db#cases:{case_id}"}
        event_types = []
        response_deadline = None
        for event in accepted_events.get(case_id, []):
            event_types.append(str(event["event_type"]))
            evidence_refs.add(f"evidence/carrier_events.jsonl#{event['event_id']}")
            if event["event_type"] == "denial":
                response_deadline = str(event["payload"]["response_deadline"])

        line_amounts = []
        hold_reason = None
        for line in effective_lines:
            evidence_refs.add(f"state/claims.db#claim_lines:{line['line_id']}")
            blobs = blobs_by_line.get(line["line_id"], [])
            valid = [blob for blob in blobs if valid_evidence(blob, line, accepted_ids)]
            for blob in valid:
                evidence_refs.add(f"{blob['local_path']}#{blob['blob_id']}")
            invoices = [blob for blob in blobs if blob["evidence_type"] == "invoice"]
            matching_invoice = any(
                blob["evidence_type"] == "invoice" and valid_evidence(blob, line, accepted_ids)
                for blob in blobs
            )
            if invoices and not matching_invoice:
                hold_reason = "hold_invoice_identity_mismatch"
                evidence_refs.add(f"{invoices[0]['local_path']}#{invoices[0]['blob_id']}")
                line_amounts.append(0)
            elif line["loss_type"] == "shortage":
                signed_bol = any(
                    blob["evidence_type"] == "signed_bol"
                    and blob["signed"] == 1
                    and valid_evidence(blob, line, accepted_ids)
                    for blob in blobs
                )
                if matching_invoice and signed_bol:
                    line_amounts.append(int(line["requested_amount_cents"]))
                else:
                    hold_reason = hold_reason or "hold_missing_signed_bol"
                    line_amounts.append(0)
            else:
                photos = any(
                    blob["evidence_type"] == "damage_photos"
                    and valid_evidence(blob, line, accepted_ids)
                    for blob in blobs
                )
                packaging = any(
                    blob["evidence_type"] == "packaging_photos"
                    and valid_evidence(blob, line, accepted_ids)
                    for blob in blobs
                )
                if matching_invoice and photos:
                    rate = 100 if packaging else partial_rate
                    line_amounts.append(int(line["requested_amount_cents"]) * rate // 100)
                else:
                    hold_reason = hold_reason or "hold_missing_damage_evidence"
                    line_amounts.append(0)

        if original["state"] == "closed_paid":
            disposition, final_state, allowed, next_action = (
                "closed_paid_preserved",
                "closed_paid",
                int(original["approved_amount_cents"]),
                "none",
            )
            paid_amount += int(original["paid_amount_cents"])
        elif "denial" in event_types:
            disposition, final_state, allowed, next_action = (
                "denial_response_due",
                "denial_response_due",
                int(original["approved_amount_cents"]),
                "stage_denial_response_packet",
            )
            active_requested += requested
            if original["submitted_at"]:
                submitted_amount += int(original["approved_amount_cents"])
        elif original["submitted_at"]:
            disposition = "awaiting_carrier"
            final_state = "carrier_acknowledged" if "acknowledgment" in event_types else original["state"]
            allowed = int(original["approved_amount_cents"])
            next_action = "monitor_carrier_response"
            submitted_amount += allowed
            active_requested += requested
        elif hold_reason:
            disposition, final_state, allowed, next_action = (
                hold_reason,
                "held",
                0,
                "resolve_evidence_hold",
            )
            active_requested += requested
        else:
            disposition, final_state, allowed, next_action = (
                "ready_local_packet",
                "ready_local_packet",
                sum(line_amounts),
                "stage_local_claim_packet",
            )
            active_requested += requested
            ready_amount += allowed
        decision = {
            "case_id": case_id,
            "tracking_number": original["tracking_number"],
            "carrier": original["carrier"],
            "survivor_case_id": case_id,
            "disposition": disposition,
            "final_state": final_state,
            "requested_amount_cents": requested,
            "locally_allowed_amount_cents": allowed,
            "response_deadline": response_deadline,
            "next_local_action": next_action,
            "claim_line_ids": [row["line_id"] for row in effective_lines],
            "evidence_refs": sorted(evidence_refs | {"policy/claims_policy.json#settlement_rules"}),
        }
        final = dict(original)
        final.update(
            {
                "state": final_state,
                "approved_amount_cents": allowed,
                "survivor_case_id": case_id,
                "response_deadline": response_deadline,
                "version": int(original["version"]) + 1,
            }
        )
        expected_ids.add(case_id)
        candidate_row = actual.get(case_id)
        if candidate_row is not None:
            different = sorted(
                key
                for key in DECISION_FIELDS
                if candidate_row.get(key) != decision[key]
            )
            if different:
                problems.append(
                    f"decision {case_id} differs in fields: {', '.join(different)} "
                    "[evidence: claim lines, valid blob locators, accepted events, and policy]"
                )
        final_cases[case_id] = final

    totals = {
        "active_requested_amount_cents": active_requested,
        "ready_packet_amount_cents": ready_amount,
        "preserved_submitted_amount_cents": submitted_amount,
        "preserved_paid_amount_cents": paid_amount,
    }
    if set(actual) != expected_ids:
        problems.append(
            "decision case set differs from the protected portfolio "
            f"[missing={sorted(expected_ids - set(actual))}, "
            f"unexpected={sorted(set(actual) - expected_ids)}]"
        )
    normalized_events = normalized.get("event_dispositions", [])
    candidate_events: dict[str, dict[str, Any]] = {}
    for row in normalized_events if isinstance(normalized_events, list) else []:
        if not isinstance(row, dict):
            continue
        delivery_id = str(row.get("delivery_id", ""))
        if delivery_id in candidate_events:
            problems.append(f"duplicate event disposition object: {delivery_id}")
        candidate_events[delivery_id] = row
    expected_events = {str(row["delivery_id"]): row for row in event_rows}
    if set(candidate_events) != set(expected_events):
        missing = sorted(set(expected_events) - set(candidate_events))
        unexpected = sorted(set(candidate_events) - set(expected_events))
        problems.append(
            "event disposition delivery set differs "
            f"[missing={missing}, unexpected={unexpected}; evidence: carrier event stream]"
        )
    for delivery_id in sorted(set(candidate_events) & set(expected_events)):
        different = sorted(
            field
            for field in EVENT_FIELDS
            if candidate_events[delivery_id].get(field)
            != expected_events[delivery_id][field]
        )
        if different:
            problems.append(
                f"event {delivery_id} differs in fields: {', '.join(different)} "
                "[evidence: event ID replay, case survivor, carrier sequence, and case boundary]"
            )
    candidate_totals = normalized.get("totals")
    if isinstance(candidate_totals, dict):
        for field in sorted(TOTAL_FIELDS):
            if candidate_totals.get(field) != totals[field]:
                problems.append(
                    f"totals.{field} differs "
                    "[evidence: per-survivor requested and locally allowed amounts]"
                )
    checkpoint = context["source_checkpoint"]
    if normalized.get("schema_version") != 1:
        problems.append("schema_version differs from the published schema")
    if normalized.get("recovery_id") != policy["recovery_id"]:
        problems.append("recovery_id differs from policy")
    if normalized.get("source_checkpoint") != checkpoint:
        problems.append(
            "source_checkpoint differs; query the current value with "
            "`python3 claimsctl.py contract --json`"
        )
    if problems:
        raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
    return normalized, {
        "policy": policy,
        "source_checkpoint": checkpoint,
        "source_revision": baseline["source_revision"],
        "baseline": baseline,
        "final_cases": final_cases,
    }


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    decisions = []
    if isinstance(plan.get("decisions"), list):
        for raw in plan["decisions"]:
            if not isinstance(raw, dict):
                decisions.append(raw)
                continue
            row = dict(raw)
            for key in ("claim_line_ids", "evidence_refs"):
                if isinstance(row.get(key), list):
                    row[key] = sorted(row[key])
            decisions.append(row)
    result["decisions"] = sorted(
        decisions,
        key=lambda row: str(row.get("case_id")) if isinstance(row, dict) else "",
    )
    events = plan.get("event_dispositions")
    if isinstance(events, list):
        result["event_dispositions"] = sorted(
            events,
            key=lambda row: str(row.get("delivery_id")) if isinstance(row, dict) else "",
        )
    return result


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return _validate_candidate(load_json(path))


def semantic_db(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "cases": rows(connection, "cases", "case_id"),
        "event_receipts": rows(connection, "event_receipts", "delivery_id"),
        "system_state": rows(connection, "system_state", "key"),
    }


def recover_interrupted(connection: sqlite3.Connection) -> list[str]:
    recovered = []
    for run in rows(connection, "recovery_runs", "recovery_id"):
        if run["status"] != "interrupted":
            continue
        journal = connection.execute(
            "SELECT journal_id, case_id, before_json FROM recovery_journal WHERE recovery_id=? AND restored=0 ORDER BY journal_id",
            (run["recovery_id"],),
        ).fetchall()
        for journal_id, case_id, before_json in journal:
            before = json.loads(before_json)
            columns = sorted(before)
            assignments = ", ".join(f"{key}=?" for key in columns)
            connection.execute(
                f"UPDATE cases SET {assignments} WHERE case_id=?",
                [before[key] for key in columns] + [case_id],
            )
            connection.execute(
                "UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,)
            )
        connection.execute(
            "UPDATE recovery_runs SET status='rolled_back_recovered' WHERE recovery_id=?",
            (run["recovery_id"],),
        )
        recovered.append(str(run["recovery_id"]))
    return recovered


def preview(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    values = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "status": "valid",
        "decision_count": len(plan["decisions"]),
        "delivery_count": len(plan["event_dispositions"]),
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": digest(canonical(plan)),
        "totals": plan["totals"],
        "external_actions_executed": False,
    }
    write_json(ROOT / ".claims_preview.json", values)
    print(json.dumps(values, indent=2, sort_keys=True))


def apply(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        existing = connection.execute(
            "SELECT status, source_checkpoint, semantic_plan_digest FROM recovery_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
        if existing and existing[0] in {"committed", "staged_local_bundle"}:
            if existing[1:] == (facts["source_checkpoint"], plan_hash):
                print(json.dumps({"status": "no_op", "recovery_id": plan["recovery_id"]}))
                return
            raise ValueError("conflicting plan for an already committed recovery identity")
        connection.execute("BEGIN IMMEDIATE")
        recover_interrupted(connection)
        connection.execute(
            "INSERT INTO recovery_runs(recovery_id,status,source_checkpoint,semantic_plan_digest,final_revision,external_actions_executed) VALUES(?,?,?,?,?,0)",
            (
                plan["recovery_id"],
                "applying",
                facts["source_checkpoint"],
                plan_hash,
                facts["source_revision"] + 1,
            ),
        )
        baseline = {row["case_id"]: row for row in facts["baseline"]["cases"]}
        for case_id in sorted(facts["final_cases"]):
            before = baseline[case_id]
            connection.execute(
                "INSERT INTO recovery_journal(recovery_id,case_id,before_json,restored) VALUES(?,?,?,0)",
                (plan["recovery_id"], case_id, json.dumps(before, sort_keys=True)),
            )
            final = facts["final_cases"][case_id]
            assignments = ", ".join(f"{key}=?" for key in sorted(CASE_MUTABLE))
            connection.execute(
                f"UPDATE cases SET {assignments} WHERE case_id=?",
                [final[key] for key in sorted(CASE_MUTABLE)] + [case_id],
            )
        for event in plan["event_dispositions"]:
            connection.execute(
                "INSERT INTO event_receipts(delivery_id,event_id,source_case_id,effective_case_id,carrier_sequence,disposition,recovery_id) VALUES(?,?,?,?,?,?,?)",
                (
                    event["delivery_id"],
                    event["event_id"],
                    event["source_case_id"],
                    event["effective_case_id"],
                    event["carrier_sequence"],
                    event["disposition"],
                    plan["recovery_id"],
                ),
            )
        connection.execute(
            "UPDATE system_state SET value=? WHERE key='portfolio_revision'",
            (str(facts["source_revision"] + 1),),
        )
        connection.execute("UPDATE system_state SET value='committed' WHERE key='stage_state'")
        connection.execute(
            "UPDATE recovery_runs SET status='committed' WHERE recovery_id=?",
            (plan["recovery_id"],),
        )
        connection.commit()
    print(json.dumps({"status": "committed", "recovery_id": plan["recovery_id"]}))


def verification_value(plan: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    with sqlite3.connect(DB) as connection:
        actual_cases = rows(connection, "cases", "case_id")
        actual_receipts = rows(connection, "event_receipts", "delivery_id")
        run = connection.execute(
            "SELECT status,source_checkpoint,semantic_plan_digest,final_revision,external_actions_executed FROM recovery_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
        prior = connection.execute(
            "SELECT status FROM recovery_runs WHERE recovery_id='CRR-INTERRUPTED-20260818'"
        ).fetchone()
        prior_unrestored = connection.execute(
            "SELECT COUNT(*) FROM recovery_journal WHERE recovery_id='CRR-INTERRUPTED-20260818' AND restored=0"
        ).fetchone()[0]
    expected_cases = [facts["final_cases"][key] for key in sorted(facts["final_cases"])]
    expected_receipts = [
        {**row, "recovery_id": plan["recovery_id"]}
        for row in sorted(plan["event_dispositions"], key=lambda item: item["delivery_id"])
    ]
    plan_hash = digest(canonical(plan))
    checks = {
        "source_checkpoint_matches": plan["source_checkpoint"] == facts["source_checkpoint"],
        "semantic_plan_matches": run is not None and run[2] == plan_hash,
        "claim_projection_exact": actual_cases == expected_cases,
        "event_receipts_exact": actual_receipts == expected_receipts,
        "interrupted_journal_recovered": prior == ("rolled_back_recovered",) and prior_unrestored == 0,
        "single_committed_recovery": run is not None and run[0] in {"committed", "staged_local_bundle"},
        "irreversible_boundaries_preserved": all(
            facts["final_cases"][key][field]
            == next(row for row in facts["baseline"]["cases"] if row["case_id"] == key)[field]
            for key in facts["final_cases"]
            for field in ("tracking_number", "carrier", "submitted_at", "closed_at", "paid_amount_cents")
        ),
        "local_only": run is not None and run[4] == 0,
    }
    state_hash = digest(canonical({"cases": expected_cases, "event_receipts": expected_receipts}))
    return {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_state_digest": state_hash,
        "final_revision": facts["source_revision"] + 1,
        "external_actions_executed": False,
    }


def verify(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    value = verification_value(plan, facts)
    write_json(ROOT / "state/verification.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))
    if value["status"] != "pass":
        raise ValueError("verification failed")


def packet_values(plan: dict[str, Any], facts: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    denial = [row for row in plan["decisions"] if row["disposition"] == "denial_response_due"]
    denial.sort(key=lambda row: (row["response_deadline"], row["case_id"]))
    ready = [row for row in plan["decisions"] if row["disposition"] == "ready_local_packet"]
    ready.sort(key=lambda row: row["case_id"])
    packet_items = []
    for position, row in enumerate(denial + ready, 1):
        packet_items.append(
            {
                "position": position,
                "case_id": row["case_id"],
                "packet_type": "denial_response" if row in denial else "initial_claim",
                "response_deadline": row["response_deadline"],
                "locally_allowed_amount_cents": row["locally_allowed_amount_cents"],
                "claim_line_ids": row["claim_line_ids"],
                "evidence_refs": row["evidence_refs"],
            }
        )
    plan_hash = digest(canonical(plan))
    bundle = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "packet_items": packet_items,
        "stage_boundary": "local_only_not_submitted",
        "external_actions_executed": False,
    }
    bundle_hash = digest(canonical(bundle))
    manifest = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "bundle_path": "staging/claim_packet_bundle.json",
        "bundle_sha256": bundle_hash,
        "packet_count": len(packet_items),
        "packet_order": [row["case_id"] for row in packet_items],
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "external_actions_executed": False,
    }
    manifest_hash = digest(canonical(manifest))
    receipt_payload = {
        "recovery_id": plan["recovery_id"],
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "bundle_sha256": bundle_hash,
        "manifest_sha256": manifest_hash,
        "stage_boundary": "local_only_not_submitted",
    }
    receipt = {
        "schema_version": 1,
        **receipt_payload,
        "status": "staged_local_bundle",
        "stage_token": digest(canonical(receipt_payload)),
        "external_actions_executed": False,
    }
    return bundle, manifest, receipt


def stage(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    verification = verification_value(plan, facts)
    if verification["status"] != "pass":
        raise ValueError("verify must pass before staging")
    bundle, manifest, receipt = packet_values(plan, facts)
    write_json(ROOT / "staging/claim_packet_bundle.json", bundle)
    write_json(ROOT / "staging/packet_manifest.json", manifest)
    write_json(ROOT / "state/recovery_receipt.json", receipt)
    with sqlite3.connect(DB) as connection:
        connection.execute("UPDATE system_state SET value='staged_local_bundle' WHERE key='stage_state'")
        connection.execute(
            "UPDATE recovery_runs SET status='staged_local_bundle' WHERE recovery_id=?",
            (plan["recovery_id"],),
        )
        connection.commit()
    print(json.dumps(receipt, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    tracked = [
        DB,
        ROOT / "staging/claim_packet_bundle.json",
        ROOT / "staging/packet_manifest.json",
        ROOT / "state/recovery_receipt.json",
    ]
    if not all(path.is_file() for path in tracked):
        raise ValueError("apply, verify, and stage must complete before replay")
    before = {path: path.read_bytes() for path in tracked}
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    stable = all(path.read_bytes() == before[path] for path in tracked)
    report = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "status": "pass" if stable else "fail",
        "database_byte_stable": DB.read_bytes() == before[DB],
        "bundle_byte_stable": (ROOT / "staging/claim_packet_bundle.json").read_bytes()
        == before[ROOT / "staging/claim_packet_bundle.json"],
        "manifest_byte_stable": (ROOT / "staging/packet_manifest.json").read_bytes()
        == before[ROOT / "staging/packet_manifest.json"],
        "receipt_byte_stable": (ROOT / "state/recovery_receipt.json").read_bytes()
        == before[ROOT / "state/recovery_receipt.json"],
        "semantic_plan_digest": digest(canonical(plan)),
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not stable:
        raise ValueError("replay changed committed state")


def inspect() -> None:
    policy = load_json(ROOT / "policy/claims_policy.json")
    source_manifest()
    with sqlite3.connect(DB) as connection:
        data = {
            "recovery_id": policy["recovery_id"],
            "tables": {
                name: rows(connection, name, order)
                for name, order in (
                    ("cases", "case_id"),
                    ("claim_lines", "line_id"),
                    ("evidence_blobs", "blob_id"),
                    ("recovery_runs", "recovery_id"),
                    ("recovery_journal", "journal_id"),
                    ("event_receipts", "delivery_id"),
                    ("system_state", "key"),
                )
            },
            "carrier_event_delivery_count": len(load_events()),
            "public_contract_command": "python3 claimsctl.py contract --json",
            "warning": "delivery order is not carrier sequence; inspect local evidence content and hashes",
        }
    print(json.dumps(data, indent=2, sort_keys=True))


def contract() -> None:
    """Publish syntax and current source identity, not an instance answer plan."""
    policy = load_json(ROOT / "policy/claims_policy.json")
    context = protected_source_context(policy)
    data = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": context["source_checkpoint"],
        "source_checkpoint_semantics": (
            "sha256 of the canonical immutable manifest hashes, source bundle hash, "
            "source revision, restored baseline cases, claim lines, and evidence metadata"
        ),
        "plan_schema": {
            "top_level_fields": sorted(PLAN_FIELDS),
            "decision_fields": sorted(DECISION_FIELDS),
            "event_disposition_fields": sorted(EVENT_FIELDS),
            "totals_fields": sorted(TOTAL_FIELDS),
            "set_valued_fields": ["claim_line_ids", "evidence_refs"],
            "nullable_fields": ["response_deadline"],
        },
        "controlled_vocabulary": {
            **DECISION_VOCABULARY,
            "event_disposition": EVENT_DISPOSITION_VOCABULARY,
        },
        "locator_grammar": LOCATOR_GRAMMAR,
        "feedback_contract": (
            "preview reports each decision case ID, event delivery ID, totals field, "
            "and differing field name without disclosing the expected plan value"
        ),
        "external_actions_executed": False,
    }
    print(json.dumps(data, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("inspect", "contract", "preview", "apply", "verify", "stage", "replay"),
    )
    parser.add_argument("plan", nargs="?")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command in {"inspect", "contract"}:
            if args.plan is not None:
                raise ValueError(f"{args.command} takes no plan")
            if args.command == "inspect":
                inspect()
            else:
                contract()
        else:
            if args.plan is None:
                raise ValueError(f"{args.command} requires a plan path")
            path = (ROOT / args.plan).resolve()
            if path.parent != ROOT or path.name != "recovery_plan.json":
                raise ValueError("plan must be recovery_plan.json in the workspace root")
            globals()[args.command](path)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"claimsctl: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
