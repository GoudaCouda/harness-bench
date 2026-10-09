#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def delivery(delivery_id: str, kind: str, control: str, po_id: str,
             revision: int, payload: dict[str, object]) -> dict[str, object]:
    return {
        "delivery_id": delivery_id,
        "sender_id": "SUPPLIER-A",
        "receiver_id": "BUYER-HQ",
        "interchange_control": f"ISA-{control}",
        "group_control": f"GS-{control}",
        "transaction_control": control,
        "message_type": kind,
        "po_id": po_id,
        "revision": revision,
        "payload": payload,
    }


def lines(*values: tuple[str, int, int]) -> list[dict[str, object]]:
    return [
        {"line_id": line_id, "quantity": quantity, "unit_price_cents": price}
        for line_id, quantity, price in values
    ]


def main() -> None:
    for name in ("edi_recovery_plan.json", ".edi_preview.json", "procurement_handoff.md"):
        (WORKSPACE / name).unlink(missing_ok=True)
    for name in ("verification.json", "recovery_receipt.json", "replay_report.json"):
        (WORKSPACE / "state" / name).unlink(missing_ok=True)
    staging = WORKSPACE / "staging"
    if staging.exists():
        for child in staging.iterdir():
            child.unlink()

    policy = {
        "schema_version": 1,
        "recovery_id": "EDI-RCV-20260819-01",
        "price_tolerance_basis_points": 200,
        "quantity_tolerance_units": 0,
        "transaction_identity_fields": ["sender_id", "receiver_id", "message_type", "transaction_control"],
        "revision_rule": "highest_revision_wins",
        "dispositions": [
            "ready_to_post_local", "hold_missing_ack", "hold_supplier_rejected",
            "hold_ack_quantity_increase", "hold_ack_price_variance",
            "hold_quantity_variance", "hold_invoice_price_mismatch", "posted_preserved",
        ],
        "event_dispositions": [
            "applied_latest_revision", "stale_revision_ignored",
            "duplicate_delivery_ignored", "control_number_collision_quarantined",
            "unknown_po_ignored", "posted_po_ignored",
        ],
        "prohibited_actions": ["transmit_edi", "post_invoice", "pay_invoice", "contact_supplier"],
    }
    write_json(WORKSPACE / "policy/match_policy.json", policy)

    order_lines = {
        "PO-1001": [("001", 10, 1000), ("002", 5, 2000)],
        "PO-1002": [("001", 10, 1000)],
        "PO-1003": [("001", 5, 3000)],
        "PO-1004": [("001", 5, 4000)],
        "PO-1005": [("001", 3, 5000)],
        "PO-1006": [("001", 2, 6000)],
        "PO-NOACK": [("001", 3, 3000)],
        "PO-POSTED": [("001", 1, 7000)],
    }
    events: list[dict[str, object]] = []
    # Keep representative 850 envelopes without repeating the same transport
    # classification for every PO. The protected database remains the order
    # authority for the other rows, as in a recovery window that starts after
    # some original orders were already persisted.
    representative_850 = {"PO-1001", "PO-1002", "PO-1005"}
    for index, (po_id, values) in enumerate(order_lines.items(), 1):
        if po_id not in representative_850:
            continue
        events.append(delivery(f"D-{index:03d}", "850", f"850-{po_id}", po_id, 1, {"lines": lines(*values)}))
    events.extend([
        delivery("D-030", "810", "810-1003", "PO-1003", 1, {"invoice_id": "INV-1003", "lines": lines(("001", 5, 3000))}),
        delivery("D-011", "855", "855-1001", "PO-1001", 1, {"status": "accepted", "lines": lines(*order_lines["PO-1001"])}),
        delivery("D-021", "856", "856-1001", "PO-1001", 1, {"shipment_id": "SHP-1001", "lines": lines(("001", 10, 0), ("002", 5, 0))}),
        delivery("D-031", "810", "810-1001", "PO-1001", 1, {"invoice_id": "INV-1001", "lines": lines(*order_lines["PO-1001"])}),
        delivery("D-012", "855", "855-1002-A", "PO-1002", 1, {"status": "accepted", "lines": lines(("001", 10, 1000))}),
        delivery("D-013", "855", "855-1002-B", "PO-1002", 2, {"status": "accepted_with_changes", "lines": lines(("001", 8, 1015))}),
        delivery("D-022", "856", "856-1002", "PO-1002", 1, {"shipment_id": "SHP-1002", "lines": lines(("001", 8, 0))}),
        delivery("D-032", "810", "810-1002", "PO-1002", 1, {"invoice_id": "INV-1002", "lines": lines(("001", 8, 1015))}),
        delivery("D-014", "855", "855-1003", "PO-1003", 1, {"status": "accepted", "lines": lines(("001", 5, 3000))}),
        delivery("D-023", "856", "856-1003", "PO-1003", 1, {"shipment_id": "SHP-1003", "lines": lines(("001", 4, 0))}),
        delivery("D-015", "855", "855-1004", "PO-1004", 1, {"status": "accepted", "lines": lines(("001", 5, 4000))}),
        delivery("D-024", "856", "856-1004", "PO-1004", 1, {"shipment_id": "SHP-1004", "lines": lines(("001", 5, 0))}),
        delivery("D-034", "810", "810-1004", "PO-1004", 1, {"invoice_id": "INV-1004", "lines": lines(("001", 5, 4125))}),
        delivery("D-016", "855", "855-1005", "PO-1005", 1, {"status": "accepted", "lines": lines(("001", 3, 5000))}),
        delivery("D-025", "856", "856-1005", "PO-1005", 1, {"shipment_id": "SHP-1005", "lines": lines(("001", 3, 0))}),
        delivery("D-035", "810", "810-1005", "PO-1005", 1, {"invoice_id": "INV-1005", "lines": lines(("001", 3, 5000))}),
        delivery("D-035-REDRIVE", "810", "810-1005", "PO-1005", 1, {"invoice_id": "INV-1005", "lines": lines(("001", 3, 5000))}),
        delivery("D-035-COLLISION", "810", "810-1005", "PO-1005", 1, {"invoice_id": "INV-1005-X", "lines": lines(("001", 3, 5500))}),
        delivery("D-017", "855", "855-1006", "PO-1006", 1, {"status": "rejected", "lines": lines(("001", 2, 6000))}),
        delivery("D-026", "856", "856-1006", "PO-1006", 1, {"shipment_id": "SHP-1006", "lines": lines(("001", 2, 0))}),
        delivery("D-036", "810", "810-1006", "PO-1006", 1, {"invoice_id": "INV-1006", "lines": lines(("001", 2, 6000))}),
        delivery("D-027", "856", "856-NOACK", "PO-NOACK", 1, {"shipment_id": "SHP-NOACK", "lines": lines(("001", 3, 0))}),
        delivery("D-037", "810", "810-NOACK", "PO-NOACK", 1, {"invoice_id": "INV-NOACK", "lines": lines(("001", 3, 3000))}),
        delivery("D-038", "810", "810-POSTED-REDRIVE", "PO-POSTED", 2, {"invoice_id": "INV-POSTED", "lines": lines(("001", 1, 7000))}),
        delivery("D-039", "810", "810-UNKNOWN", "PO-UNKNOWN", 1, {"invoice_id": "INV-UNKNOWN", "lines": lines(("001", 1, 9900))}),
    ])
    events = events[5:14] + events[:5] + events[14:]
    edi = WORKSPACE / "evidence/edi_deliveries.jsonl"
    edi.parent.mkdir(parents=True, exist_ok=True)
    edi.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")

    state = WORKSPACE / "state"
    state.mkdir(parents=True, exist_ok=True)
    database = state / "procurement.db"
    database.unlink(missing_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript("""
        CREATE TABLE purchase_orders(po_id TEXT PRIMARY KEY,buyer_id TEXT NOT NULL,supplier_id TEXT NOT NULL,currency TEXT NOT NULL,state TEXT NOT NULL,matched_amount_cents INTEGER NOT NULL,held_amount_cents INTEGER NOT NULL,hold_reason TEXT,version INTEGER NOT NULL,issued_at TEXT NOT NULL,posted_invoice_id TEXT,posted_at TEXT);
        CREATE TABLE po_lines(line_id TEXT PRIMARY KEY,po_id TEXT NOT NULL,sku TEXT NOT NULL,ordered_qty INTEGER NOT NULL,unit_price_cents INTEGER NOT NULL);
        CREATE TABLE edi_receipts(delivery_id TEXT PRIMARY KEY,message_type TEXT NOT NULL,transaction_control TEXT NOT NULL,po_id TEXT NOT NULL,revision INTEGER NOT NULL,disposition TEXT NOT NULL,recovery_id TEXT NOT NULL);
        CREATE TABLE match_results(po_id TEXT NOT NULL,line_id TEXT NOT NULL,recovery_id TEXT NOT NULL,acknowledged_qty INTEGER NOT NULL,shipped_qty INTEGER NOT NULL,invoiced_qty INTEGER NOT NULL,acknowledged_unit_price_cents INTEGER NOT NULL,invoiced_unit_price_cents INTEGER NOT NULL,match_status TEXT NOT NULL,PRIMARY KEY(po_id,line_id));
        CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY,source_checkpoint TEXT NOT NULL,semantic_plan_sha256 TEXT NOT NULL,status TEXT NOT NULL,stage_token TEXT);
        CREATE TABLE recovery_journal(journal_id TEXT PRIMARY KEY,recovery_id TEXT NOT NULL,po_id TEXT NOT NULL,before_json TEXT NOT NULL,restored INTEGER NOT NULL);
        CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        po_rows, line_rows = [], []
        for po_id, values in order_lines.items():
            posted = po_id == "PO-POSTED"
            po_rows.append((po_id, "BUYER-HQ", "SUPPLIER-A", "USD", "posted" if posted else "open", 7000 if posted else 0, 0, None, 1, "2026-08-15T12:00:00Z", "INV-POSTED" if posted else None, "2026-08-18T09:30:00Z" if posted else None))
            for line_id, quantity, price in values:
                line_rows.append((f"{po_id}:{line_id}", po_id, f"SKU-{po_id[-4:]}-{line_id}", quantity, price))
        connection.executemany("INSERT INTO purchase_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", po_rows)
        connection.executemany("INSERT INTO po_lines VALUES(?,?,?,?,?)", line_rows)
        columns = [row[1] for row in connection.execute("PRAGMA table_info(purchase_orders)")]
        before = dict(zip(columns, connection.execute("SELECT * FROM purchase_orders WHERE po_id='PO-1004'").fetchone(), strict=True))
        connection.execute("UPDATE purchase_orders SET state='ready_to_post_local',matched_amount_cents=20000,version=2 WHERE po_id='PO-1004'")
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?)", ("EDI-INTERRUPTED-00", "partial", "partial", "interrupted", None))
        connection.execute("INSERT INTO recovery_journal VALUES(?,?,?,?,?)", ("J-INT-001", "EDI-INTERRUPTED-00", "PO-1004", json.dumps(before, sort_keys=True), 0))
        connection.executemany("INSERT INTO system_state VALUES(?,?)", [("source_revision", "12"), ("last_successful_batch", "2026-08-18T08:00:00Z")])
        connection.commit()

    manifest_files = {
        "policy/match_policy.json": digest((WORKSPACE / "policy/match_policy.json").read_bytes()),
        "evidence/edi_deliveries.jsonl": digest(edi.read_bytes()),
    }
    write_json(WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": manifest_files})


if __name__ == "__main__":
    main()
