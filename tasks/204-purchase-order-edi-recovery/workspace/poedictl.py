#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/procurement.db"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "po_decisions",
    "event_dispositions", "totals", "external_actions_executed",
}
DECISION_FIELDS = {
    "po_id", "supplier_id", "disposition", "final_state",
    "ordered_amount_cents", "invoice_amount_cents", "matched_amount_cents",
    "held_amount_cents", "ack_revision", "next_local_action", "line_matches",
    "evidence_refs",
}
LINE_FIELDS = {
    "line_id", "ordered_qty", "acknowledged_qty", "shipped_qty",
    "invoiced_qty", "ordered_unit_price_cents",
    "acknowledged_unit_price_cents", "invoiced_unit_price_cents", "match_status",
}
EVENT_FIELDS = {
    "delivery_id", "message_type", "transaction_control", "po_id", "revision",
    "disposition",
}
TOTAL_FIELDS = {
    "active_ordered_amount_cents", "ready_payable_amount_cents",
    "held_invoice_amount_cents", "preserved_posted_amount_cents",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain one object")
    return value


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def source_manifest() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source_manifest.json is malformed")
    changed = []
    for locator, expected in files.items():
        path = ROOT / str(locator)
        actual = digest(path.read_bytes()) if path.is_file() else "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def load_deliveries() -> list[dict[str, Any]]:
    result = []
    try:
        source = (ROOT / "evidence/edi_deliveries.jsonl").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read EDI deliveries: {exc}") from exc
    for number, line in enumerate(source.splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed EDI delivery line {number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"EDI delivery line {number} is not an object")
        result.append(value)
    return result


def normalized(plan: dict[str, Any]) -> dict[str, Any]:
    value = dict(plan)
    decisions = []
    for raw in plan.get("po_decisions", []) if isinstance(plan.get("po_decisions"), list) else []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        if isinstance(row.get("evidence_refs"), list):
            row["evidence_refs"] = sorted(row["evidence_refs"])
        if isinstance(row.get("line_matches"), list):
            row["line_matches"] = sorted(row["line_matches"], key=lambda item: str(item.get("line_id")))
        decisions.append(row)
    value["po_decisions"] = sorted(decisions, key=lambda row: str(row.get("po_id")))
    dispositions = plan.get("event_dispositions", [])
    value["event_dispositions"] = sorted(
        [dict(row) for row in dispositions if isinstance(row, dict)],
        key=lambda row: str(row.get("delivery_id")),
    ) if isinstance(dispositions, list) else []
    return value


def baseline_state(connection: sqlite3.Connection, recovery_id: str) -> dict[str, Any]:
    orders = {row["po_id"]: row for row in rows(connection, "purchase_orders", "po_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs", "recovery_id")}
    journal = rows(connection, "recovery_journal", "journal_id")
    current = runs.get(recovery_id)
    if current and current["status"] in {"committed", "staged_local"}:
        for row in journal:
            if row["recovery_id"] == recovery_id:
                orders[row["po_id"]] = json.loads(row["before_json"])
    for row in journal:
        run = runs.get(row["recovery_id"])
        if run and run["status"] == "interrupted" and not row["restored"]:
            orders[row["po_id"]] = json.loads(row["before_json"])
    system = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
    return {
        "purchase_orders": [orders[key] for key in sorted(orders)],
        "po_lines": rows(connection, "po_lines", "line_id"),
        "source_revision": int(system.get("source_revision", "0")),
    }


def message_fingerprint(event: dict[str, Any]) -> str:
    return digest(canonical({key: value for key, value in event.items() if key != "delivery_id"}))


def event_context(
    deliveries: list[dict[str, Any]],
    orders: dict[str, dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    problems: list[dict[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Validate submitted delivery dispositions and return only source events."""
    identities: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for event in deliveries:
        identity = tuple(str(event.get(field, "")) for field in ("sender_id", "receiver_id", "message_type", "transaction_control"))
        identities.setdefault(identity, []).append(event)
    accepted: list[dict[str, Any]] = []
    disposition_by_delivery: dict[str, str] = {}
    for members in identities.values():
        fingerprints = Counter(message_fingerprint(row) for row in members)
        winner = min(fingerprints, key=lambda key: (-fingerprints[key], key))
        winner_members = sorted((row for row in members if message_fingerprint(row) == winner), key=lambda row: str(row["delivery_id"]))
        accepted.append(winner_members[0])
        for row in winner_members[1:]:
            disposition_by_delivery[str(row["delivery_id"])] = "duplicate_delivery_ignored"
        for row in members:
            if message_fingerprint(row) != winner:
                disposition_by_delivery[str(row["delivery_id"])] = "control_number_collision_quarantined"

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    known_candidates: list[dict[str, Any]] = []
    for event in accepted:
        delivery_id = str(event["delivery_id"])
        po_id = str(event.get("po_id", ""))
        if po_id not in orders:
            disposition_by_delivery[delivery_id] = "unknown_po_ignored"
        elif orders[po_id]["state"] == "posted":
            disposition_by_delivery[delivery_id] = "posted_po_ignored"
        else:
            known_candidates.append(event)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in known_candidates:
        groups.setdefault((str(event["po_id"]), str(event["message_type"])), []).append(event)
    for key, members in groups.items():
        ordered = sorted(members, key=lambda row: (int(row.get("revision", -1)), str(row["transaction_control"]), str(row["delivery_id"])))
        latest[key] = ordered[-1]
        for row in ordered[:-1]:
            disposition_by_delivery[str(row["delivery_id"])] = "stale_revision_ignored"
        disposition_by_delivery[str(ordered[-1]["delivery_id"])] = "applied_latest_revision"

    submitted = {str(row.get("delivery_id")): row for row in candidate_rows}
    if set(submitted) != {str(row.get("delivery_id", "")) for row in deliveries}:
        problems.append({"scope": "events", "id": "set", "field": "delivery_ids", "evidence": "EDI delivery identity"})
    for event in deliveries:
        delivery_id = str(event.get("delivery_id", ""))
        required = {
            "delivery_id": str(event.get("delivery_id", "")),
            "message_type": str(event.get("message_type", "")),
            "transaction_control": str(event.get("transaction_control", "")),
            "po_id": str(event.get("po_id", "")),
            "revision": int(event.get("revision", -1)),
            "disposition": disposition_by_delivery[delivery_id],
        }
        row = submitted.get(delivery_id)
        for field in EVENT_FIELDS:
            if not isinstance(row, dict) or row.get(field) != required[field]:
                problems.append({"scope": "event", "id": delivery_id, "field": field, "evidence": "EDI identity, duplicate, and revision ordering"})
    return latest


def line_map(event: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not event or not isinstance(event.get("payload"), dict):
        return {}
    values = event["payload"].get("lines", [])
    return {str(row.get("line_id")): row for row in values if isinstance(row, dict)} if isinstance(values, list) else {}


def validation_report(candidate: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Check a submitted plan without returning a completed plan or final state."""
    policy = load_json(ROOT / "policy/match_policy.json")
    manifest, source_bundle_hash = source_manifest()
    deliveries = load_deliveries()
    recovery_id = str(policy["recovery_id"])
    with sqlite3.connect(DB) as connection:
        baseline = baseline_state(connection, recovery_id)
    orders = {row["po_id"]: row for row in baseline["purchase_orders"]}
    lines_by_po: dict[str, list[dict[str, Any]]] = {}
    for row in baseline["po_lines"]:
        lines_by_po.setdefault(row["po_id"], []).append(row)
    problems: list[dict[str, str]] = []
    schema_ok = (
        set(candidate) == PLAN_FIELDS
        and isinstance(candidate.get("po_decisions"), list)
        and all(isinstance(row, dict) and set(row) == DECISION_FIELDS for row in candidate.get("po_decisions", []))
        and all(isinstance(row.get("line_matches"), list) for row in candidate.get("po_decisions", []) if isinstance(row, dict))
        and all(isinstance(line, dict) and set(line) == LINE_FIELDS for row in candidate.get("po_decisions", []) for line in row.get("line_matches", []) if isinstance(row.get("line_matches"), list))
        and isinstance(candidate.get("event_dispositions"), list)
        and all(isinstance(row, dict) and set(row) == EVENT_FIELDS for row in candidate.get("event_dispositions", []))
        and isinstance(candidate.get("totals"), dict)
        and set(candidate.get("totals", {})) == TOTAL_FIELDS
    )
    if not schema_ok:
        problems.append({"scope": "plan", "id": "schema", "field": "fields", "evidence": "published plan schema"})
    candidate = normalized(candidate)
    decision_rows = candidate.get("po_decisions", []) if schema_ok else []
    event_rows = candidate.get("event_dispositions", []) if schema_ok else []
    latest = event_context(deliveries, orders, event_rows, problems)
    submitted = {str(row.get("po_id")): row for row in decision_rows}
    if set(submitted) != set(orders):
        problems.append({"scope": "purchase_orders", "id": "set", "field": "po_ids", "evidence": "restored purchase-order baseline"})
    totals = {
        "active_ordered_amount_cents": 0,
        "ready_payable_amount_cents": 0,
        "held_invoice_amount_cents": 0,
        "preserved_posted_amount_cents": 0,
    }
    tolerance = int(policy["price_tolerance_basis_points"])
    quantity_tolerance = int(policy["quantity_tolerance_units"])
    for po_id in sorted(orders):
        order = orders[po_id]
        po_lines = sorted(lines_by_po.get(po_id, []), key=lambda row: row["line_id"])
        ordered_amount = sum(int(row["ordered_qty"]) * int(row["unit_price_cents"]) for row in po_lines)
        refs = {"policy/match_policy.json#three_way_match", f"state/procurement.db#purchase_orders:{po_id}"}
        refs.update(f"state/procurement.db#po_lines:{row['line_id']}" for row in po_lines)
        refs.update(
            f"evidence/edi_deliveries.jsonl#{row['delivery_id']}"
            for row in deliveries
            if str(row.get("po_id", "")) == po_id
        )

        if order["state"] == "posted":
            line_matches = [{
                "line_id": row["line_id"], "ordered_qty": row["ordered_qty"],
                "acknowledged_qty": row["ordered_qty"], "shipped_qty": row["ordered_qty"],
                "invoiced_qty": row["ordered_qty"], "ordered_unit_price_cents": row["unit_price_cents"],
                "acknowledged_unit_price_cents": row["unit_price_cents"],
                "invoiced_unit_price_cents": row["unit_price_cents"], "match_status": "posted_preserved",
            } for row in po_lines]
            disposition = final_state = "posted_preserved"
            invoice_amount = matched_amount = int(order["matched_amount_cents"])
            held_amount, ack_revision, next_action = 0, None, "none"
            totals["preserved_posted_amount_cents"] += matched_amount
        else:
            totals["active_ordered_amount_cents"] += ordered_amount
            ack = latest.get((po_id, "855"))
            shipment = latest.get((po_id, "856"))
            invoice = latest.get((po_id, "810"))
            ack_lines, shipment_lines, invoice_lines = line_map(ack), line_map(shipment), line_map(invoice)
            ack_status = str(ack.get("payload", {}).get("status", "")) if ack else ""
            ack_revision = int(ack["revision"]) if ack else None
            line_matches = []
            reasons: list[str] = []
            for base in po_lines:
                short_id = str(base["line_id"]).split(":")[-1]
                acknowledged = ack_lines.get(short_id, {})
                shipped = shipment_lines.get(short_id, {})
                invoiced = invoice_lines.get(short_id, {})
                aq = int(acknowledged.get("quantity", 0))
                sq = int(shipped.get("quantity", 0))
                iq = int(invoiced.get("quantity", 0))
                op = int(base["unit_price_cents"])
                ap = int(acknowledged.get("unit_price_cents", 0))
                ip = int(invoiced.get("unit_price_cents", 0))
                if not ack:
                    status = "hold_missing_ack"
                elif ack_status == "rejected":
                    status = "hold_supplier_rejected"
                elif aq > int(base["ordered_qty"]) + quantity_tolerance:
                    status = "hold_ack_quantity_increase"
                elif abs(ap - op) * 10000 > op * tolerance:
                    status = "hold_ack_price_variance"
                elif iq > aq + quantity_tolerance or iq > sq + quantity_tolerance:
                    status = "hold_quantity_variance"
                elif ip != ap:
                    status = "hold_invoice_price_mismatch"
                else:
                    status = "matched"
                if status != "matched":
                    reasons.append(status)
                line_matches.append({
                    "line_id": base["line_id"], "ordered_qty": int(base["ordered_qty"]),
                    "acknowledged_qty": aq, "shipped_qty": sq, "invoiced_qty": iq,
                    "ordered_unit_price_cents": op, "acknowledged_unit_price_cents": ap,
                    "invoiced_unit_price_cents": ip, "match_status": status,
                })
            invoice_amount = sum(row["invoiced_qty"] * row["invoiced_unit_price_cents"] for row in line_matches)
            if reasons:
                disposition = reasons[0]
                final_state = disposition
                matched_amount, held_amount = 0, invoice_amount
                next_action = {
                    "hold_missing_ack": "obtain_authoritative_855",
                    "hold_supplier_rejected": "route_to_buyer_for_supplier_rejection",
                    "hold_ack_quantity_increase": "route_to_buyer_for_ack_quantity_variance",
                    "hold_ack_price_variance": "route_to_buyer_for_ack_price_variance",
                    "hold_quantity_variance": "await_receipt_or_corrected_invoice",
                    "hold_invoice_price_mismatch": "request_corrected_invoice_locally",
                }[disposition]
                totals["held_invoice_amount_cents"] += held_amount
            else:
                disposition = final_state = "ready_to_post_local"
                matched_amount, held_amount = invoice_amount, 0
                next_action = "review_local_payable_batch"
                totals["ready_payable_amount_cents"] += matched_amount
        required = {
            "po_id": po_id, "supplier_id": order["supplier_id"], "disposition": disposition,
            "final_state": final_state, "ordered_amount_cents": ordered_amount,
            "invoice_amount_cents": invoice_amount, "matched_amount_cents": matched_amount,
            "held_amount_cents": held_amount, "ack_revision": ack_revision,
            "next_local_action": next_action, "line_matches": line_matches,
            "evidence_refs": sorted(refs),
        }
        submitted_row = submitted.get(po_id)
        for field in DECISION_FIELDS:
            if not isinstance(submitted_row, dict) or submitted_row.get(field) != required[field]:
                problems.append({"scope": "purchase_order", "id": po_id, "field": field, "evidence": "order, EDI event, line-match, and policy facts"})

    checkpoint_payload = {
        "manifest_files": manifest["files"], "source_bundle_hash": source_bundle_hash,
        "source_revision": baseline["source_revision"],
        "purchase_orders": baseline["purchase_orders"], "po_lines": baseline["po_lines"],
    }
    checkpoint = digest(canonical(checkpoint_payload))
    for field, valid, evidence in (
        ("schema_version", candidate.get("schema_version") == 1, "published plan schema"),
        ("recovery_id", candidate.get("recovery_id") == recovery_id, "published recovery policy"),
        ("source_checkpoint", candidate.get("source_checkpoint") == checkpoint, "protected source bundle and restored baseline"),
        ("external_actions_executed", candidate.get("external_actions_executed") is False, "local-only execution boundary"),
    ):
        if not valid:
            problems.append({"scope": "plan", "id": recovery_id, "field": field, "evidence": evidence})
    submitted_totals = candidate.get("totals", {})
    for field, value in totals.items():
        if not isinstance(submitted_totals, dict) or submitted_totals.get(field) != value:
            problems.append({"scope": "totals", "id": recovery_id, "field": field, "evidence": "independently recomputed order and invoice amounts"})
    return problems, {"baseline": baseline, "source_checkpoint": checkpoint}


def validated(path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidate = load_json(path)
    problems, facts = validation_report(candidate)
    if problems:
        raise ValueError(json.dumps({"status": "invalid", "discrepancies": problems}, sort_keys=True))
    return candidate, normalized(candidate), facts


def command_inspect() -> None:
    manifest_error = None
    try:
        source_manifest()
    except ValueError as exc:
        manifest_error = str(exc)
    with sqlite3.connect(DB) as connection:
        table_counts = {name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("purchase_orders", "po_lines", "edi_receipts", "match_results", "recovery_runs", "recovery_journal")}
        interrupted = rows(connection, "recovery_journal", "journal_id")
    deliveries = load_deliveries()
    print(json.dumps({"source_valid": manifest_error is None, "source_error": manifest_error, "table_counts": table_counts, "delivery_count": len(deliveries), "message_types": dict(Counter(str(row.get("message_type")) for row in deliveries)), "journal": interrupted}, indent=2, sort_keys=True))


def command_preview(path: Path) -> None:
    candidate = load_json(path)
    problems, _ = validation_report(candidate)
    report = {
        "status": "valid" if not problems else "invalid",
        "recovery_id": candidate.get("recovery_id"), "source_checkpoint": candidate.get("source_checkpoint"),
        "semantic_plan_sha256": digest(canonical(normalized(candidate))),
        "discrepancies": problems,
    }
    write_json(ROOT / ".edi_preview.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "valid":
        raise ValueError("preview rejected")


def current_run(recovery_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(DB) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM recovery_runs WHERE recovery_id=?", (recovery_id,)).fetchone()
    return dict(row) if row else None


def command_apply(path: Path) -> None:
    raw = load_json(path)
    candidate = normalized(raw)
    run = current_run(str(candidate.get("recovery_id", "")))
    plan_hash = digest(canonical(candidate))
    if run:
        if run["semantic_plan_sha256"] != plan_hash:
            raise ValueError("semantic_plan_conflict: committed identity has different content")
        print(json.dumps({"status": "idempotent", "recovery_id": candidate["recovery_id"]}, sort_keys=True))
        return
    _, candidate, facts = validated(path)
    baseline_orders = {row["po_id"]: row for row in facts["baseline"]["purchase_orders"]}
    with sqlite3.connect(DB) as connection:
        connection.execute("BEGIN IMMEDIATE")
        interrupted = connection.execute("SELECT journal_id,po_id,before_json FROM recovery_journal WHERE restored=0 AND recovery_id IN (SELECT recovery_id FROM recovery_runs WHERE status='interrupted') ORDER BY journal_id").fetchall()
        for journal_id, po_id, before_json in interrupted:
            before = json.loads(before_json)
            fields = [key for key in before if key != "po_id"]
            connection.execute(f"UPDATE purchase_orders SET {','.join(f'{field}=?' for field in fields)} WHERE po_id=?", [before[field] for field in fields] + [po_id])
            connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
        for decision in candidate["po_decisions"]:
            po_id = decision["po_id"]
            before = baseline_orders[po_id]
            if before["state"] == "posted":
                continue
            connection.execute("INSERT INTO recovery_journal VALUES(?,?,?,?,?)", (f"J-{candidate['recovery_id']}-{po_id}", candidate["recovery_id"], po_id, json.dumps(before, sort_keys=True), 1))
            hold_reason = None if decision["final_state"] == "ready_to_post_local" else decision["disposition"]
            connection.execute("UPDATE purchase_orders SET state=?,matched_amount_cents=?,held_amount_cents=?,hold_reason=?,version=? WHERE po_id=?", (decision["final_state"], decision["matched_amount_cents"], decision["held_amount_cents"], hold_reason, int(before["version"]) + 1, po_id))
        connection.execute("DELETE FROM edi_receipts")
        connection.executemany("INSERT INTO edi_receipts VALUES(?,?,?,?,?,?,?)", [(row["delivery_id"], row["message_type"], row["transaction_control"], row["po_id"], row["revision"], row["disposition"], candidate["recovery_id"]) for row in candidate["event_dispositions"]])
        connection.execute("DELETE FROM match_results")
        for decision in candidate["po_decisions"]:
            if baseline_orders[decision["po_id"]]["state"] == "posted":
                continue
            for line in decision["line_matches"]:
                connection.execute(
                    "INSERT INTO match_results VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        decision["po_id"], line["line_id"], candidate["recovery_id"],
                        line["acknowledged_qty"], line["shipped_qty"], line["invoiced_qty"],
                        line["acknowledged_unit_price_cents"], line["invoiced_unit_price_cents"],
                        line["match_status"],
                    ),
                )
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?)", (candidate["recovery_id"], candidate["source_checkpoint"], plan_hash, "committed", None))
        connection.commit()
    print(json.dumps({"status": "committed", "recovery_id": candidate["recovery_id"]}, sort_keys=True))


def database_projection() -> dict[str, Any]:
    with sqlite3.connect(DB) as connection:
        return {
            "purchase_orders": rows(connection, "purchase_orders", "po_id"),
            "po_lines": rows(connection, "po_lines", "line_id"),
            "edi_receipts": rows(connection, "edi_receipts", "delivery_id"),
            "match_results": rows(connection, "match_results", "po_id,line_id"),
            "recovery_journal": rows(connection, "recovery_journal", "journal_id"),
            "recovery_runs": rows(connection, "recovery_runs", "recovery_id"),
            "system_state": rows(connection, "system_state", "key"),
        }


def command_verify(path: Path) -> None:
    _, candidate, facts = validated(path)
    run = current_run(candidate["recovery_id"])
    expected_orders = {
        row["po_id"]: dict(row) for row in facts["baseline"]["purchase_orders"]
    }
    expected_matches = []
    for decision in candidate["po_decisions"]:
        original = expected_orders[decision["po_id"]]
        if original["state"] == "posted":
            continue
        original.update(
            state=decision["final_state"],
            matched_amount_cents=decision["matched_amount_cents"],
            held_amount_cents=decision["held_amount_cents"],
            hold_reason=None if decision["final_state"] == "ready_to_post_local" else decision["disposition"],
            version=int(original["version"]) + 1,
        )
        for line in decision["line_matches"]:
            expected_matches.append({
                "po_id": decision["po_id"], "line_id": line["line_id"],
                "recovery_id": candidate["recovery_id"],
                "acknowledged_qty": line["acknowledged_qty"], "shipped_qty": line["shipped_qty"],
                "invoiced_qty": line["invoiced_qty"],
                "acknowledged_unit_price_cents": line["acknowledged_unit_price_cents"],
                "invoiced_unit_price_cents": line["invoiced_unit_price_cents"],
                "match_status": line["match_status"],
            })
    expected_matches.sort(key=lambda row: (row["po_id"], row["line_id"]))
    projection = database_projection()
    actual_orders = {row["po_id"]: row for row in projection["purchase_orders"]}
    checks = {
        "run_committed": bool(run and run["status"] in {"committed", "staged_local"}),
        "purchase_order_projection": actual_orders == expected_orders,
        "line_match_projection": projection["match_results"] == expected_matches,
        "journal_restored": all(row["restored"] == 1 for row in projection["recovery_journal"]),
        "posted_boundary_preserved": actual_orders.get("PO-POSTED") == expected_orders.get("PO-POSTED"),
    }
    report = {
        "schema_version": 1, "status": "verified" if all(checks.values()) else "invalid",
        "recovery_id": candidate["recovery_id"], "source_checkpoint": candidate["source_checkpoint"],
        "semantic_plan_sha256": digest(canonical(candidate)), "state_sha256": digest(canonical(projection)),
        "checks": checks, "external_actions_executed": False,
    }
    write_json(ROOT / "state/verification.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] != "verified":
        raise ValueError("verification failed")


def command_stage(path: Path) -> None:
    _, candidate, _ = validated(path)
    verification = load_json(ROOT / "state/verification.json")
    handoff = ROOT / "procurement_handoff.md"
    if verification.get("status") != "verified" or not handoff.is_file():
        raise ValueError("verified state and procurement_handoff.md are required")
    payable = {
        "schema_version": 1, "recovery_id": candidate["recovery_id"],
        "items": [{"po_id": row["po_id"], "amount_cents": row["matched_amount_cents"], "action": "review_for_posting"} for row in candidate["po_decisions"] if row["final_state"] == "ready_to_post_local"],
        "external_actions_executed": False,
    }
    holds = {
        "schema_version": 1, "recovery_id": candidate["recovery_id"],
        "items": [{"po_id": row["po_id"], "held_amount_cents": row["held_amount_cents"], "reason": row["disposition"], "next_local_action": row["next_local_action"]} for row in candidate["po_decisions"] if str(row["final_state"]).startswith("hold_")],
        "external_actions_executed": False,
    }
    write_json(ROOT / "staging/payable_batch.json", payable)
    write_json(ROOT / "staging/hold_queue.json", holds)
    core = {
        "schema_version": 1, "recovery_id": candidate["recovery_id"],
        "source_checkpoint": candidate["source_checkpoint"],
        "semantic_plan_sha256": digest(canonical(candidate)),
        "payable_batch_sha256": digest(canonical(payable)), "hold_queue_sha256": digest(canonical(holds)),
        "verification_sha256": digest(canonical(verification)), "handoff_sha256": digest(handoff.read_bytes()),
        "external_actions_executed": False,
    }
    manifest = {**core, "stage_token": digest(canonical(core))}
    write_json(ROOT / "staging/stage_manifest.json", manifest)
    receipt = {"schema_version": 1, "recovery_id": candidate["recovery_id"], "stage_token": manifest["stage_token"], "status": "staged_local_only", "external_actions_executed": False}
    write_json(ROOT / "state/recovery_receipt.json", receipt)
    with sqlite3.connect(DB) as connection:
        connection.execute("UPDATE recovery_runs SET status='staged_local',stage_token=? WHERE recovery_id=?", (manifest["stage_token"], candidate["recovery_id"]))
        connection.commit()
    print(json.dumps(receipt, sort_keys=True))


def command_replay(path: Path) -> None:
    raw = load_json(path)
    candidate = normalized(raw)
    plan_hash = digest(canonical(candidate))
    run = current_run(str(candidate.get("recovery_id", "")))
    if not run or run["semantic_plan_sha256"] != plan_hash:
        raise ValueError("semantic_plan_conflict or missing committed identity")
    manifest_path = ROOT / "staging/stage_manifest.json"
    if run["status"] != "staged_local" or not manifest_path.is_file():
        raise ValueError("staged local closure is required")
    report = {
        "schema_version": 1, "status": "idempotent", "recovery_id": candidate["recovery_id"],
        "semantic_plan_sha256": plan_hash, "database_byte_stable": True,
        "stage_manifest_sha256": digest(manifest_path.read_bytes()),
    }
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("inspect", "preview", "apply", "verify", "stage", "replay"))
    parser.add_argument("plan", nargs="?", default="edi_recovery_plan.json")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            command_inspect()
        else:
            path = (ROOT / args.plan).resolve()
            if path.parent != ROOT:
                raise ValueError("plan must be a workspace-root file")
            {"preview": command_preview, "apply": command_apply, "verify": command_verify, "stage": command_stage, "replay": command_replay}[args.command](path)
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
