#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/billing.db"
PLAN_FIELDS = {
    "schema_version",
    "recovery_id",
    "source_checkpoint",
    "billing_cycle",
    "decisions",
    "external_actions_executed",
    "customer_contacted",
}
DECISION_FIELDS = {
    "account_id",
    "meter_id",
    "authority_method",
    "correction_state",
    "billed_import_kwh",
    "billed_export_kwh",
    "correct_import_kwh",
    "correct_export_kwh",
    "delta_import_kwh",
    "delta_export_kwh",
    "prospective_balance_delta_cents",
    "local_mutations",
    "evidence_refs",
    "next_local_action",
    "external_action",
}
MUTABLE_BILL_FIELDS = {
    "corrected_import_kwh",
    "corrected_export_kwh",
    "billing_state",
    "prospective_balance_delta_cents",
}
NUMERIC_FIELDS = {
    "billed_import_kwh",
    "billed_export_kwh",
    "correct_import_kwh",
    "correct_export_kwh",
    "delta_import_kwh",
    "delta_export_kwh",
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
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def rows(
    connection: sqlite3.Connection, table: str, order: str
) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def source_bundle() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source manifest is malformed")
    changed = []
    for locator, expected in files.items():
        path = ROOT / str(locator)
        try:
            actual = digest(path.read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def load_interval_events() -> list[dict[str, Any]]:
    path = ROOT / "evidence/interval_feed.jsonl"
    events: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read interval feed: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed interval line {line_number}") from exc
        if not isinstance(event, dict) or not event.get("event_id"):
            raise ValueError(f"invalid interval line {line_number}")
        event_id = str(event["event_id"])
        existing = events.get(event_id)
        if existing and {
            key: value for key, value in existing.items() if key != "sequence"
        } != {key: value for key, value in event.items() if key != "sequence"}:
            raise ValueError(f"conflicting retransmission for {event_id}")
        if not existing or int(event.get("sequence", 0)) > int(
            existing.get("sequence", 0)
        ):
            events[event_id] = event
    return sorted(
        events.values(),
        key=lambda item: (str(item["meter_id"]), str(item["interval_start_utc"])),
    )


def load_fallback() -> dict[str, Any]:
    trust = load_json(ROOT / "evidence/fallback_trust.json")
    raw = load_json(ROOT / "evidence/fallback_batch.json")
    payload = {
        key: value
        for key, value in raw.items()
        if key not in {"key_id", "payload_checksum", "signature"}
    }
    checksum = digest(canonical(payload))
    signature = digest(
        canonical(payload) + str(trust.get("verification_material", "")).encode()
    )
    if (
        raw.get("key_id") != trust.get("key_id")
        or raw.get("payload_checksum") != checksum
        or raw.get("signature") != signature
    ):
        raise ValueError("fallback checksum or signature verification failed")
    return payload


def primary_is_damaged() -> bool:
    try:
        json.loads(
            (ROOT / "evidence/primary_batch.json.part").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True
    return False


def register_rows() -> dict[str, dict[str, str]]:
    try:
        with (ROOT / "evidence/register_reads.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            reader = csv.DictReader(handle)
            required = {
                "read_id",
                "meter_id",
                "cycle",
                "start_register",
                "end_register",
                "modulus",
                "quality",
            }
            if set(reader.fieldnames or []) != required:
                raise ValueError("register read schema differs")
            return {str(row["meter_id"]): dict(row) for row in reader}
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"cannot read register evidence: {exc}") from exc


def source_baseline(
    connection: sqlite3.Connection, recovery_id: str
) -> tuple[list[dict[str, Any]], int]:
    bills = {row["meter_id"]: row for row in rows(connection, "bills", "meter_id")}
    runs = {
        row["recovery_id"]: row
        for row in rows(connection, "correction_runs", "recovery_id")
    }
    journal = rows(connection, "correction_journal", "journal_id")
    current = runs.get(recovery_id)
    if current and current["status"] in {"committed", "staged_pending_review"}:
        for row in journal:
            if row["recovery_id"] == recovery_id:
                bills[row["meter_id"]] = json.loads(row["before_json"])
    for row in journal:
        run = runs.get(row["recovery_id"])
        if run and run["status"] == "interrupted" and not row["restored"]:
            bills[row["meter_id"]] = json.loads(row["before_json"])
    state = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
    revision = int(
        state.get("source_billing_revision", state.get("billing_revision", "0"))
    )
    return [bills[key] for key in sorted(bills)], revision


def round_energy(value: float) -> float:
    return round(float(value) + 0.0, 3)


def normalized_plan(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    normalized = []
    if isinstance(value.get("decisions"), list):
        for raw in value["decisions"]:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            for key in ("local_mutations", "evidence_refs"):
                if isinstance(row.get(key), list):
                    row[key] = sorted(set(str(item) for item in row[key]))
            for key in NUMERIC_FIELDS:
                if row.get(key) is not None and isinstance(row.get(key), (int, float)):
                    row[key] = round_energy(float(row[key]))
            normalized.append(row)
    result["decisions"] = sorted(normalized, key=lambda item: str(item.get("meter_id")))
    return result


def recovery_inputs() -> dict[str, Any]:
    """Load verified billing evidence without constructing a recovery answer."""
    policy = load_json(ROOT / "policy/billing_policy.json")
    manifest, source_bundle_hash = source_bundle()
    interval_events = load_interval_events()
    registers = register_rows()
    fallback = load_fallback()
    if not primary_is_damaged():
        raise ValueError("primary batch is parseable; fallback is not authorized")
    with sqlite3.connect(DB) as connection:
        baseline, source_revision = source_baseline(
            connection, str(policy["recovery_id"])
        )
    baseline_by_meter = {row["meter_id"]: row for row in baseline}
    events_by_meter: dict[str, list[dict[str, Any]]] = {}
    for event in interval_events:
        events_by_meter.setdefault(str(event["meter_id"]), []).append(event)
    fallback_by_meter = {
        str(row["meter_id"]): row
        for row in fallback.get("records", [])
        if isinstance(row, dict) and row.get("meter_id")
    }
    checkpoint = digest(
        canonical(
            {
                "immutable_source_hashes": manifest["files"],
                "source_bundle_hash": source_bundle_hash,
                "source_billing_revision": source_revision,
                "baseline_bills": baseline,
            }
        )
    )
    return {
        "policy": policy,
        "baseline": baseline,
        "baseline_by_meter": baseline_by_meter,
        "events_by_meter": events_by_meter,
        "registers": registers,
        "fallback_by_meter": fallback_by_meter,
        "fallback_batch_id": fallback["batch_id"],
        "source_revision": source_revision,
        "source_checkpoint": checkpoint,
    }


def validate_plan(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    candidate = normalized_plan(load_json(plan_path))
    inputs = recovery_inputs()
    policy = inputs["policy"]
    top_level_fields: list[str] = []
    if set(candidate) != PLAN_FIELDS:
        top_level_fields.append("schema")
    required_top = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": inputs["source_checkpoint"],
        "billing_cycle": policy["billing_cycle"],
        "external_actions_executed": False,
        "customer_contacted": False,
    }
    top_level_fields.extend(
        key for key, value in required_top.items() if candidate.get(key) != value
    )
    rows_value = candidate.get("decisions")
    decisions = rows_value if isinstance(rows_value, list) else []
    if not isinstance(rows_value, list) or any(
        not isinstance(row, dict) or set(row) != DECISION_FIELDS for row in decisions
    ):
        top_level_fields.append("decisions_schema")
    by_meter = {
        str(row.get("meter_id")): row for row in decisions if isinstance(row, dict)
    }
    meter_fields: dict[str, list[str]] = {}
    if len(by_meter) != len(decisions):
        top_level_fields.append("duplicate_meter_ids")
    for scope in sorted(policy["meters"], key=lambda item: item["meter_id"]):
        meter_id = str(scope["meter_id"])
        account_id = str(scope["account_id"])
        bill = inputs["baseline_by_meter"].get(meter_id)
        if (
            not bill
            or bill["account_id"] != account_id
            or bill["cycle"] != policy["billing_cycle"]
        ):
            raise ValueError(f"billing identity mismatch for {meter_id}")
        method = str(scope["authority_method"])
        refs = ["policy/billing_policy.json#meters/" + meter_id]
        correct_import: float | None
        correct_export: float | None
        if method in {"interval_utc_deduplicated", "bidirectional_interval"}:
            usable = [
                event
                for event in inputs["events_by_meter"].get(meter_id, [])
                if event.get("quality") == "actual"
                and event.get("cycle") == policy["billing_cycle"]
            ]
            utc_keys = [str(event["interval_start_utc"]) for event in usable]
            if len(usable) != int(scope["expected_interval_count"]) or len(
                set(utc_keys)
            ) != len(utc_keys):
                raise ValueError(f"interval coverage invalid for {meter_id}")
            if method == "interval_utc_deduplicated":
                local_groups: dict[str, set[str]] = {}
                for event in usable:
                    local_groups.setdefault(str(event["local_start"]), set()).add(
                        str(event["utc_offset"])
                    )
                if not any(len(offsets) == 2 for offsets in local_groups.values()):
                    raise ValueError("fall-back offset pair is missing")
            correct_import = round_energy(
                sum(float(event["import_kwh"]) for event in usable)
            )
            correct_export = round_energy(
                sum(float(event["export_kwh"]) for event in usable)
            )
            refs.extend(
                f"evidence/interval_feed.jsonl#{event['event_id']}" for event in usable
            )
        elif method == "register_rollover":
            register = inputs["registers"].get(meter_id)
            if (
                not register
                or register["quality"] != "actual"
                or register["cycle"] != policy["billing_cycle"]
            ):
                raise ValueError(f"register authority invalid for {meter_id}")
            start, end, modulus = (
                float(register[key])
                for key in ("start_register", "end_register", "modulus")
            )
            correct_import = round_energy(
                end - start if end >= start else modulus - start + end
            )
            correct_export = 0.0
            refs.append(f"evidence/register_reads.csv#{register['read_id']}")
        elif method == "signed_fallback_snapshot":
            record = inputs["fallback_by_meter"].get(meter_id)
            if (
                not record
                or record.get("cycle") != policy["billing_cycle"]
                or record.get("quality") != "validated_actual"
            ):
                raise ValueError(f"signed fallback lacks valid record for {meter_id}")
            correct_import = round_energy(float(record["import_kwh"]))
            correct_export = round_energy(float(record["export_kwh"]))
            refs.extend(
                [
                    "evidence/primary_batch.json.part#damaged",
                    f"evidence/fallback_batch.json#{record['record_id']}",
                    "evidence/fallback_trust.json#meter-batch-key-2026",
                ]
            )
        elif method == "insufficient_evidence":
            usable = [
                event
                for event in inputs["events_by_meter"].get(meter_id, [])
                if event.get("quality") == "actual"
            ]
            if len(usable) >= int(scope["minimum_complete_intervals"]):
                raise ValueError(f"hold evidence unexpectedly complete for {meter_id}")
            correct_import = None
            correct_export = None
            refs.extend(
                f"evidence/interval_feed.jsonl#{event['event_id']}"
                for event in inputs["events_by_meter"].get(meter_id, [])
            )
        else:
            raise ValueError(f"unsupported authority method {method}")
        billed_import = round_energy(float(bill["billed_import_kwh"]))
        billed_export = round_energy(float(bill["billed_export_kwh"]))
        if correct_import is None:
            delta_import = delta_export = None
            balance_delta = 0
            correction_state = "hold_insufficient_evidence"
            next_action = "obtain_authoritative_meter_evidence"
        else:
            delta_import = round_energy(correct_import - billed_import)
            delta_export = round_energy(correct_export - billed_export)
            balance_delta = round(
                (delta_import - delta_export) * int(bill["rate_cents_per_kwh"])
            )
            correction_state = "correction_pending_review"
            next_action = "route_local_correction_for_billing_review"
        projected = dict(bill)
        projected.update(
            {
                "corrected_import_kwh": correct_import,
                "corrected_export_kwh": correct_export,
                "billing_state": correction_state,
                "prospective_balance_delta_cents": balance_delta,
                "version": int(bill["version"]) + 1,
            }
        )
        mutations = sorted(
            key for key in MUTABLE_BILL_FIELDS if projected.get(key) != bill.get(key)
        )
        required = {
            "account_id": account_id,
            "meter_id": meter_id,
            "authority_method": method,
            "correction_state": correction_state,
            "billed_import_kwh": billed_import,
            "billed_export_kwh": billed_export,
            "correct_import_kwh": correct_import,
            "correct_export_kwh": correct_export,
            "delta_import_kwh": delta_import,
            "delta_export_kwh": delta_export,
            "prospective_balance_delta_cents": balance_delta,
            "local_mutations": mutations,
            "evidence_refs": sorted(refs),
            "next_local_action": next_action,
            "external_action": "none",
        }
        got = by_meter.get(meter_id)
        differing = sorted(
            field
            for field in DECISION_FIELDS
            if not isinstance(got, dict) or got.get(field) != required[field]
        )
        if differing:
            meter_fields[meter_id] = differing
    required_ids = {str(row["meter_id"]) for row in policy["meters"]}
    for meter_id in sorted(set(by_meter) - required_ids):
        meter_fields[meter_id] = ["unexpected_meter"]
    if set(by_meter) != required_ids:
        top_level_fields.append("meter_coverage")
    if top_level_fields or meter_fields:
        diagnostics = {
            "top_level_fields": sorted(set(top_level_fields)),
            "meter_fields": meter_fields,
        }
        raise ValueError(
            "plan differs from authority/policy state; diagnostics="
            + json.dumps(diagnostics, sort_keys=True, separators=(",", ":"))
        )
    facts = {
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": inputs["source_checkpoint"],
        "baseline": inputs["baseline"],
        "source_revision": inputs["source_revision"],
        "fallback_batch_id": inputs["fallback_batch_id"],
    }
    return candidate, facts, digest(canonical(candidate))


def preview(plan_path: Path) -> None:
    plan, facts, plan_hash = validate_plan(plan_path)
    decisions = plan["decisions"]
    report = {
        "schema_version": 1,
        "recovery_id": facts["recovery_id"],
        "status": "valid",
        "primary_batch_rejected_as_damaged": True,
        "fallback_checksum_verified": True,
        "fallback_signature_verified": True,
        "decision_count": len(decisions),
        "correction_count": sum(
            row["correction_state"] == "correction_pending_review" for row in decisions
        ),
        "hold_count": sum(
            row["correction_state"] == "hold_insufficient_evidence" for row in decisions
        ),
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "external_actions_executed": False,
        "customer_contacted": False,
    }
    write_json(ROOT / ".meter_preview.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def apply_candidate_fields(
    bill: dict[str, Any], decision: dict[str, Any]
) -> None:
    """Apply one already validated candidate decision to a caller-owned row."""
    bill.update(
        {
            "corrected_import_kwh": decision["correct_import_kwh"],
            "corrected_export_kwh": decision["correct_export_kwh"],
            "billing_state": decision["correction_state"],
            "prospective_balance_delta_cents": decision[
                "prospective_balance_delta_cents"
            ],
            "version": int(bill["version"]) + 1,
        }
    )


def logical_db_digest(plan: dict[str, Any], facts: dict[str, Any]) -> str:
    baseline = {row["meter_id"]: row for row in facts["baseline"]}
    decisions = {row["meter_id"]: row for row in plan["decisions"]}
    projected = []
    for meter_id in sorted(baseline):
        row = dict(baseline[meter_id])
        apply_candidate_fields(row, decisions[meter_id])
        projected.append(row)
    return digest(
        canonical({"bills": projected})
    )


def apply(plan_path: Path) -> None:
    plan, facts, plan_hash = validate_plan(plan_path)
    recovery_id = str(plan["recovery_id"])
    db_hash = logical_db_digest(plan, facts)
    with sqlite3.connect(DB) as connection:
        connection.row_factory = sqlite3.Row
        existing = connection.execute(
            "SELECT * FROM correction_runs WHERE recovery_id=?", (recovery_id,)
        ).fetchone()
        if existing:
            if (
                existing["semantic_plan_digest"] != plan_hash
                or existing["source_checkpoint"] != plan["source_checkpoint"]
            ):
                raise ValueError("conflicting plan for stable recovery identity")
            if existing["status"] in {"committed", "staged_pending_review"}:
                print(
                    json.dumps(
                        {"status": "no_op", "recovery_id": recovery_id}, sort_keys=True
                    )
                )
                return
            raise ValueError("recovery identity exists in a non-replayable state")
        connection.execute("BEGIN IMMEDIATE")
        interrupted = connection.execute(
            "SELECT recovery_id FROM correction_runs WHERE status='interrupted' ORDER BY recovery_id"
        ).fetchall()
        for run in interrupted:
            prior_id = str(run["recovery_id"])
            journal_rows = connection.execute(
                "SELECT journal_id, meter_id, before_json FROM correction_journal WHERE recovery_id=? AND restored=0 ORDER BY journal_id",
                (prior_id,),
            ).fetchall()
            for item in journal_rows:
                before = json.loads(item["before_json"])
                connection.execute(
                    """UPDATE bills SET account_id=?, cycle=?, billed_import_kwh=?, billed_export_kwh=?,
                    corrected_import_kwh=?, corrected_export_kwh=?, billing_state=?,
                    prospective_balance_delta_cents=?, rate_cents_per_kwh=?, invoice_state=?, version=?
                    WHERE meter_id=?""",
                    (
                        before["account_id"],
                        before["cycle"],
                        before["billed_import_kwh"],
                        before["billed_export_kwh"],
                        before["corrected_import_kwh"],
                        before["corrected_export_kwh"],
                        before["billing_state"],
                        before["prospective_balance_delta_cents"],
                        before["rate_cents_per_kwh"],
                        before["invoice_state"],
                        before["version"],
                        item["meter_id"],
                    ),
                )
                connection.execute(
                    "UPDATE correction_journal SET restored=1 WHERE journal_id=?",
                    (item["journal_id"],),
                )
            connection.execute(
                "UPDATE correction_runs SET status='rolled_back_recovered' WHERE recovery_id=?",
                (prior_id,),
            )
        connection.execute(
            """INSERT INTO correction_runs
            (recovery_id,status,source_checkpoint,semantic_plan_digest,semantic_db_digest,
             final_revision,external_actions_executed,customer_contacted)
            VALUES (?,?,?,?,?,?,0,0)""",
            (
                recovery_id,
                "committed",
                plan["source_checkpoint"],
                plan_hash,
                db_hash,
                int(facts["source_revision"]) + 1,
            ),
        )
        baseline_by_meter = {row["meter_id"]: row for row in facts["baseline"]}
        decisions_by_meter = {row["meter_id"]: row for row in plan["decisions"]}
        for meter_id in sorted(baseline_by_meter):
            before = baseline_by_meter[meter_id]
            after = dict(before)
            apply_candidate_fields(after, decisions_by_meter[meter_id])
            connection.execute(
                "INSERT INTO correction_journal (recovery_id,meter_id,before_json,after_json,restored) VALUES (?,?,?,?,0)",
                (
                    recovery_id,
                    meter_id,
                    canonical(before).decode().strip(),
                    canonical(after).decode().strip(),
                ),
            )
            connection.execute(
                """UPDATE bills SET corrected_import_kwh=?, corrected_export_kwh=?, billing_state=?,
                prospective_balance_delta_cents=?, version=? WHERE meter_id=?""",
                (
                    after["corrected_import_kwh"],
                    after["corrected_export_kwh"],
                    after["billing_state"],
                    after["prospective_balance_delta_cents"],
                    after["version"],
                    meter_id,
                ),
            )
        connection.execute(
            "UPDATE system_state SET value=? WHERE key='billing_revision'",
            (str(int(facts["source_revision"]) + 1),),
        )
        connection.execute(
            "UPDATE system_state SET value='not_staged' WHERE key='stage_state'"
        )
        connection.commit()
    print(
        json.dumps(
            {
                "status": "committed",
                "recovery_id": recovery_id,
                "recovered_runs": len(interrupted),
            },
            sort_keys=True,
        )
    )


def current_state(
    plan: dict[str, Any], facts: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    recovery_id = str(facts["recovery_id"])
    with sqlite3.connect(DB) as connection:
        actual_bills = rows(connection, "bills", "meter_id")
        runs = {
            row["recovery_id"]: row
            for row in rows(connection, "correction_runs", "recovery_id")
        }
        journal = rows(connection, "correction_journal", "journal_id")
        state = dict(
            connection.execute("SELECT key, value FROM system_state").fetchall()
        )
    baseline = {row["meter_id"]: row for row in facts["baseline"]}
    decisions = {row["meter_id"]: row for row in plan["decisions"]}
    projected_bills = []
    for meter_id in sorted(baseline):
        row = dict(baseline[meter_id])
        apply_candidate_fields(row, decisions[meter_id])
        projected_bills.append(row)
    current = runs.get(recovery_id, {})
    prior = runs.get("MBR-INTERRUPTED-20261116", {})
    own_journal = [row for row in journal if row["recovery_id"] == recovery_id]
    prior_journal = [
        row for row in journal if row["recovery_id"] == "MBR-INTERRUPTED-20261116"
    ]
    checks = {
        "bills_exact": actual_bills == projected_bills,
        "interrupted_journal_recovered": prior.get("status") == "rolled_back_recovered"
        and len(prior_journal) == 1
        and prior_journal[0]["restored"] == 1,
        "single_committed_recovery": len(own_journal) == len(projected_bills)
        and current.get("status") in {"committed", "staged_pending_review"},
        "source_revision_advanced_once": state.get("billing_revision")
        == str(int(facts["source_revision"]) + 1),
        "invoices_not_issued": all(
            row["invoice_state"] == "estimated_unissued" for row in actual_bills
        ),
        "local_only": current.get("external_actions_executed") == 0
        and current.get("customer_contacted") == 0,
    }
    return all(checks.values()), checks


def verify(plan_path: Path) -> None:
    plan, facts, plan_hash = validate_plan(plan_path)
    ok, checks = current_state(plan, facts)
    report = {
        "schema_version": 1,
        "recovery_id": facts["recovery_id"],
        "status": "pass" if ok else "fail",
        "checks": checks,
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_db_digest": logical_db_digest(plan, facts),
        "final_revision": int(facts["source_revision"]) + 1,
        "external_actions_executed": False,
        "customer_contacted": False,
    }
    write_json(ROOT / "state/verification.json", report)
    if not ok:
        raise ValueError(
            "verification failed: "
            + ", ".join(key for key, value in checks.items() if not value)
        )
    print(json.dumps(report, indent=2, sort_keys=True))


def stage(plan_path: Path) -> None:
    plan, facts, plan_hash = validate_plan(plan_path)
    ok, _ = current_state(plan, facts)
    if not ok:
        raise ValueError("cannot stage an unverified recovery")
    verification = load_json(ROOT / "state/verification.json")
    if (
        verification.get("status") != "pass"
        or verification.get("semantic_plan_digest") != plan_hash
    ):
        raise ValueError("run verify before stage")
    token_input = {
        "recovery_id": facts["recovery_id"],
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_db_digest": logical_db_digest(plan, facts),
        "verification_hash": digest(canonical(verification)),
        "stage_boundary": "local_only_pending_meter_and_billing_review",
    }
    receipt = {
        "schema_version": 1,
        **token_input,
        "status": "staged_pending_review",
        "stage_token": digest(canonical(token_input)),
        "external_actions_executed": False,
        "customer_contacted": False,
    }
    receipt_path = ROOT / "state/recovery_receipt.json"
    existing_receipt = load_json(receipt_path) if receipt_path.exists() else None
    if existing_receipt is not None and existing_receipt != receipt:
        raise ValueError("existing receipt conflicts with this recovery")
    with sqlite3.connect(DB) as connection:
        status = connection.execute(
            "SELECT status FROM correction_runs WHERE recovery_id=?",
            (facts["recovery_id"],),
        ).fetchone()
        if not status:
            raise ValueError("recovery run is missing")
        if status[0] == "committed":
            connection.execute(
                "UPDATE correction_runs SET status='staged_pending_review' WHERE recovery_id=?",
                (facts["recovery_id"],),
            )
            connection.execute(
                "UPDATE system_state SET value='staged_pending_review' WHERE key='stage_state'"
            )
            connection.commit()
        elif status[0] != "staged_pending_review":
            raise ValueError("recovery run cannot be staged")
    if existing_receipt is None:
        write_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    db_before = DB.read_bytes()
    receipt_path = ROOT / "state/recovery_receipt.json"
    receipt_before = receipt_path.read_bytes()
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    report = {
        "schema_version": 1,
        "recovery_id": load_json(plan_path)["recovery_id"],
        "status": "pass",
        "database_byte_stable": DB.read_bytes() == db_before,
        "receipt_byte_stable": receipt_path.read_bytes() == receipt_before,
        "single_committed_recovery": True,
        "external_actions_executed": False,
        "customer_contacted": False,
    }
    if not report["database_byte_stable"] or not report["receipt_byte_stable"]:
        raise ValueError("semantic replay changed database or receipt")
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def inspect(as_json: bool) -> None:
    policy = load_json(ROOT / "policy/billing_policy.json")
    try:
        fallback = load_fallback()
        fallback_ok = True
    except ValueError:
        fallback, fallback_ok = {}, False
    events = load_interval_events()
    with sqlite3.connect(DB) as connection:
        bills = rows(connection, "bills", "meter_id")
        runs = rows(connection, "correction_runs", "recovery_id")
        state = dict(
            connection.execute("SELECT key, value FROM system_state").fetchall()
        )
    result = {
        "recovery_id": policy.get("recovery_id"),
        "billing_cycle": policy.get("billing_cycle"),
        "source_checkpoint": recovery_inputs()["source_checkpoint"],
        "primary_batch_damaged": primary_is_damaged(),
        "fallback_checksum_and_signature_valid": fallback_ok,
        "fallback_batch_id": fallback.get("batch_id"),
        "raw_interval_lines": len(
            (ROOT / "evidence/interval_feed.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ),
        "deduplicated_interval_events": len(events),
        "bills": [
            {
                key: row[key]
                for key in (
                    "account_id",
                    "meter_id",
                    "billing_state",
                    "invoice_state",
                    "version",
                )
            }
            for row in bills
        ],
        "runs": [
            {"recovery_id": row["recovery_id"], "status": row["status"]} for row in runs
        ],
        "system_state": state,
    }
    output = (
        json.dumps(result, indent=2, sort_keys=True)
        if as_json
        else "\n".join(f"{key}: {value}" for key, value in result.items())
    )
    print(output)


def query(table: str) -> None:
    allowed = {
        "bills": "meter_id",
        "correction_runs": "recovery_id",
        "correction_journal": "journal_id",
        "system_state": "key",
    }
    if table not in allowed:
        raise ValueError("query table must be one of: " + ", ".join(sorted(allowed)))
    with sqlite3.connect(DB) as connection:
        print(
            json.dumps(
                rows(connection, table, allowed[table]), indent=2, sort_keys=True
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Guarded offline smart-meter billing recovery controller"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("table")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("plan")
    args = parser.parse_args()
    if args.command == "inspect":
        inspect(args.json)
    elif args.command == "query":
        query(args.table)
    else:
        globals()[args.command]((ROOT / args.plan).resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
