#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def payload_hash(row: dict[str, object]) -> str:
    return hashlib.sha256(canonical(row)).hexdigest()


def event(event_id: str, subscription_id: str, invoice_id: str, sequence: int,
          kind: str, occurred_at: str, data: dict[str, object]) -> dict[str, object]:
    return {
        "event_id": event_id,
        "subscription_id": subscription_id,
        "invoice_id": invoice_id,
        "provider_sequence": sequence,
        "type": kind,
        "occurred_at": occurred_at,
        "data": data,
    }


def create_database(path: Path) -> None:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        CREATE TABLE customers (
          customer_id TEXT PRIMARY KEY, email_hash TEXT NOT NULL, region TEXT NOT NULL
        );
        CREATE TABLE subscriptions (
          subscription_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
          plan_code TEXT NOT NULL, status TEXT NOT NULL, seats INTEGER NOT NULL,
          current_period_end TEXT NOT NULL, version INTEGER NOT NULL
        );
        CREATE TABLE invoices (
          invoice_id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL,
          total_cents INTEGER NOT NULL, paid_cents INTEGER NOT NULL,
          refunded_cents INTEGER NOT NULL, dispute_status TEXT NOT NULL,
          status TEXT NOT NULL, version INTEGER NOT NULL
        );
        CREATE TABLE entitlements (
          subscription_id TEXT PRIMARY KEY, plan_code TEXT NOT NULL,
          state TEXT NOT NULL, seats INTEGER NOT NULL, valid_until TEXT NOT NULL,
          version INTEGER NOT NULL
        );
        CREATE TABLE processed_events (
          event_id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL,
          provider_sequence INTEGER NOT NULL, source TEXT NOT NULL,
          payload_hash TEXT NOT NULL, run_id TEXT NOT NULL
        );
        CREATE TABLE quarantined_events (
          event_id TEXT PRIMARY KEY, reason TEXT NOT NULL,
          payload_hash TEXT NOT NULL, run_id TEXT NOT NULL
        );
        CREATE TABLE recovery_runs (
          run_id TEXT PRIMARY KEY, status TEXT NOT NULL, plan_hash TEXT NOT NULL,
          source_bundle_hash TEXT NOT NULL, semantic_db_hash TEXT NOT NULL,
          revision INTEGER NOT NULL, external_actions_executed INTEGER NOT NULL
        );
        CREATE TABLE rollback_rows (
          run_id TEXT NOT NULL, table_name TEXT NOT NULL, record_key TEXT NOT NULL,
          before_json TEXT NOT NULL, restored INTEGER NOT NULL,
          PRIMARY KEY (run_id, table_name, record_key)
        );
        CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    customers = [
        ("cus_orchid", hashlib.sha256(b"orchid@example.invalid").hexdigest(), "NA"),
        ("cus_amber", hashlib.sha256(b"amber@example.invalid").hexdigest(), "EU"),
        ("cus_cobalt", hashlib.sha256(b"cobalt@example.invalid").hexdigest(), "NA"),
        ("cus_dahlia", hashlib.sha256(b"dahlia@example.invalid").hexdigest(), "APAC"),
    ]
    subscriptions = [
        ("sub_orchid", "cus_orchid", "pro", "active", 7, "2026-08-31T23:59:59Z", 6),
        ("sub_amber", "cus_amber", "pro", "active", 5, "2026-09-30T23:59:59Z", 4),
        ("sub_cobalt", "cus_cobalt", "team", "past_due", 4, "2026-09-30T23:59:59Z", 4),
        ("sub_dahlia", "cus_dahlia", "basic", "active", 2, "2026-08-31T23:59:59Z", 2),
    ]
    invoices = [
        ("inv_orchid", "sub_orchid", 12000, 12000, 0, "none", "paid", 6),
        ("inv_amber", "sub_amber", 20000, 20000, 0, "none", "paid", 4),
        ("inv_cobalt", "sub_cobalt", 9000, 0, 0, "none", "payment_failed", 4),
        ("inv_dahlia", "sub_dahlia", 6000, 6000, 0, "none", "paid", 2),
    ]
    entitlements = [
        ("sub_orchid", "starter", "grace", 3, "2026-08-31T23:59:59Z", 5),
        ("sub_amber", "pro", "active", 5, "2026-09-30T23:59:59Z", 4),
        ("sub_cobalt", "team", "suspended", 0, "2026-09-30T23:59:59Z", 4),
        ("sub_dahlia", "basic", "active", 2, "2026-08-31T23:59:59Z", 2),
    ]
    connection.executemany("INSERT INTO customers VALUES (?,?,?)", customers)
    connection.executemany("INSERT INTO subscriptions VALUES (?,?,?,?,?,?,?)", subscriptions)
    connection.executemany("INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?)", invoices)
    connection.executemany("INSERT INTO entitlements VALUES (?,?,?,?,?,?)", entitlements)
    prior_run = "ER-INTERRUPTED-20260817"
    connection.execute(
        "INSERT INTO recovery_runs VALUES (?,?,?,?,?,?,?)",
        (prior_run, "applying", "stale-plan", "stale-source", "", 18, 0),
    )
    before_rows = {
        ("subscriptions", "sub_orchid"): {
            "subscription_id": "sub_orchid", "customer_id": "cus_orchid",
            "plan_code": "starter", "status": "past_due", "seats": 3,
            "current_period_end": "2026-08-31T23:59:59Z", "version": 5,
        },
        ("invoices", "inv_orchid"): {
            "invoice_id": "inv_orchid", "subscription_id": "sub_orchid",
            "total_cents": 12000, "paid_cents": 0, "refunded_cents": 0,
            "dispute_status": "none", "status": "open", "version": 5,
        },
        ("entitlements", "sub_orchid"): {
            "subscription_id": "sub_orchid", "plan_code": "starter",
            "state": "grace", "seats": 3,
            "valid_until": "2026-08-31T23:59:59Z", "version": 5,
        },
    }
    connection.executemany(
        "INSERT INTO rollback_rows VALUES (?,?,?,?,0)",
        [(prior_run, table, key, json.dumps(value, sort_keys=True)) for (table, key), value in before_rows.items()],
    )
    partial_events = [
        ("evt_O101", "sub_orchid", 1, "webhook_spool", "partial-o101", prior_run),
        ("evt_O104", "sub_orchid", 4, "webhook_spool", "partial-o104", prior_run),
    ]
    connection.executemany("INSERT INTO processed_events VALUES (?,?,?,?,?,?)", partial_events)
    connection.executemany(
        "INSERT INTO system_state VALUES (?,?)",
        [("projection_revision", "17"), ("stage_state", "recovery_required")],
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def generate_inputs() -> None:
    for name in ("policy", "evidence", "state"):
        (WORKSPACE / name).mkdir(parents=True, exist_ok=True)
    trust = {
        "schema_version": 1,
        "key_id": "synthetic-provider-snapshot-2026",
        "algorithm": "sha256-canonical-json-plus-verification-material",
        "verification_material": "offline-synthetic-verifier-113-v1",
    }
    write_json(WORKSPACE / "evidence/provider_trust.json", trust)
    rows = [
        event("evt_C303", "sub_cobalt", "inv_cobalt", 3, "invoice_paid", "2026-08-16T09:20:00Z", {"amount_cents": 9000}),
        event("evt_O104", "sub_orchid", "inv_orchid", 4, "subscription_updated", "2026-08-12T15:00:00Z", {"plan_code": "pro", "seats": 7}),
        event("evt_X901", "sub_unknown", "inv_unknown", 1, "invoice_paid", "2026-08-17T01:00:00Z", {"amount_cents": 5000}),
        event("evt_A202", "sub_amber", "inv_amber", 2, "chargeback_lost", "2026-08-01T10:00:00Z", {"amount_cents": 20000}),
        event("evt_D401", "sub_dahlia", "inv_dahlia", 1, "cancellation_scheduled", "2026-08-10T13:00:00Z", {"effective_at": "2026-08-31T23:59:59Z"}),
        event("evt_O101", "sub_orchid", "inv_orchid", 1, "invoice_paid", "2026-08-10T12:00:00Z", {"amount_cents": 12000}),
        event("evt_C301", "sub_cobalt", "inv_cobalt", 1, "invoice_payment_failed", "2026-08-14T09:00:00Z", {"grace_until": "2026-08-17T00:00:00Z"}),
        event("evt_C303", "sub_cobalt", "inv_cobalt", 3, "invoice_paid", "2026-08-16T09:20:00Z", {"amount_cents": 9000}),
        event("evt_O103", "sub_orchid", "inv_orchid", 3, "refund_partially_completed", "2026-08-12T14:00:00Z", {"amount_cents": 2500}),
        event("evt_A201", "sub_amber", "inv_amber", 1, "chargeback_opened", "2026-07-15T10:00:00Z", {"amount_cents": 20000, "grace_until": "2026-07-22T10:00:00Z"}),
    ]
    (WORKSPACE / "evidence/webhook_spool.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )
    bridge_events = [
        event("evt_O102", "sub_orchid", "inv_orchid", 2, "invoice_finalized", "2026-08-10T11:55:00Z", {"total_cents": 12000}),
        event("evt_C302", "sub_cobalt", "inv_cobalt", 2, "payment_retry_scheduled", "2026-08-15T09:00:00Z", {"attempt": 2}),
    ]
    body = {
        "schema_version": 1,
        "snapshot_id": "psnap_20260818_0900",
        "generated_at": "2026-08-18T09:00:00Z",
        "known_subscription_high_watermarks": {
            "sub_orchid": 4, "sub_amber": 2, "sub_cobalt": 3, "sub_dahlia": 1
        },
        "bridge_events": bridge_events,
    }
    snapshot = dict(body)
    snapshot["signature"] = hashlib.sha256(canonical(body) + trust["verification_material"].encode()).hexdigest()
    snapshot["key_id"] = trust["key_id"]
    write_json(WORKSPACE / "evidence/provider_snapshot.json", snapshot)
    policy = {
        "schema_version": 1,
        "run_id": "ER-20260818-01",
        "as_of": "2026-08-18T09:00:00Z",
        "snapshot_required_for_sequence_gaps": True,
        "duplicate_key": "event_id",
        "event_order_key": "provider_sequence",
        "money_unit": "integer_cents",
        "partial_refund_changes_seats": False,
        "verified_payment_supersedes_failure": True,
        "full_lost_chargeback_entitlement_rule": "suspend_only_after_grace_until",
        "scheduled_cancellation_rule": "keep_active_until_current_period_end",
        "unknown_subscription_rule": "quarantine_without_projection_mutation",
        "subscription_status_vocabulary": ["active", "delinquent", "cancel_at_period_end"],
        "invoice_status_vocabulary": ["paid", "partially_refunded", "charged_back"],
        "dispute_status_vocabulary": ["none", "lost"],
        "entitlement_state_vocabulary": ["active", "suspended"],
        "next_local_action_vocabulary": [
            "support_review_partial_refund", "manual_billing_review",
            "close_recovered_payment_incident", "review_at_period_end"
        ],
        "stage_boundary": "local_only_pending_support_approval",
        "prohibited_external_actions": [
            "provider_refund", "provider_cancel", "provider_entitlement_update",
            "customer_notification", "customer_contact"
        ],
    }
    write_json(WORKSPACE / "policy/recovery_policy.json", policy)
    create_database(WORKSPACE / "state/billing.db")
    static_names = [
        "policy/recovery_policy.json", "evidence/webhook_spool.jsonl",
        "evidence/provider_snapshot.json", "evidence/provider_trust.json",
        "entitlementctl.py",
    ]
    hashes = {name: hashlib.sha256((WORKSPACE / name).read_bytes()).hexdigest() for name in static_names}
    write_json(WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": hashes})


def generate_reference() -> None:
    with tempfile.TemporaryDirectory(prefix="hb113-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        decisions = [
            {
                "subscription_id": "sub_orchid", "invoice_id": "inv_orchid",
                "source_high_watermark": 4, "subscription_status": "active",
                "invoice_status": "partially_refunded", "paid_cents": 12000,
                "refunded_cents": 2500, "dispute_status": "none",
                "entitlement_state": "active", "plan_code": "pro", "seats": 7,
                "event_ids": ["evt_O101", "evt_O102", "evt_O103", "evt_O104"],
                "bridged_event_ids": ["evt_O102"], "duplicate_event_ids": [],
                "next_local_action": "support_review_partial_refund", "external_action": "none",
            },
            {
                "subscription_id": "sub_amber", "invoice_id": "inv_amber",
                "source_high_watermark": 2, "subscription_status": "delinquent",
                "invoice_status": "charged_back", "paid_cents": 20000,
                "refunded_cents": 0, "dispute_status": "lost",
                "entitlement_state": "suspended", "plan_code": "pro", "seats": 0,
                "event_ids": ["evt_A201", "evt_A202"], "bridged_event_ids": [],
                "duplicate_event_ids": [], "next_local_action": "manual_billing_review",
                "external_action": "none",
            },
            {
                "subscription_id": "sub_cobalt", "invoice_id": "inv_cobalt",
                "source_high_watermark": 3, "subscription_status": "active",
                "invoice_status": "paid", "paid_cents": 9000,
                "refunded_cents": 0, "dispute_status": "none",
                "entitlement_state": "active", "plan_code": "team", "seats": 4,
                "event_ids": ["evt_C301", "evt_C302", "evt_C303"],
                "bridged_event_ids": ["evt_C302"], "duplicate_event_ids": ["evt_C303"],
                "next_local_action": "close_recovered_payment_incident", "external_action": "none",
            },
            {
                "subscription_id": "sub_dahlia", "invoice_id": "inv_dahlia",
                "source_high_watermark": 1, "subscription_status": "cancel_at_period_end",
                "invoice_status": "paid", "paid_cents": 6000,
                "refunded_cents": 0, "dispute_status": "none",
                "entitlement_state": "active", "plan_code": "basic", "seats": 2,
                "event_ids": ["evt_D401"], "bridged_event_ids": [],
                "duplicate_event_ids": [], "next_local_action": "review_at_period_end",
                "external_action": "none",
            },
        ]
        plan = {
            "schema_version": 1, "run_id": "ER-20260818-01",
            "snapshot_id": "psnap_20260818_0900", "decisions": decisions,
            "quarantined_event_ids": ["evt_X901"], "external_actions_executed": False,
        }
        write_json(workspace / "recovery_plan.json", plan)
        for command in ("preview", "apply", "verify", "stage", "replay"):
            completed = subprocess.run(
                ["python3", "entitlementctl.py", command, "recovery_plan.json"],
                cwd=workspace, check=False, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"{command} failed:\n{completed.stdout}")
        (workspace / "recovery_handoff.md").write_text(
            """# Subscription entitlement recovery handoff

The signed `psnap_20260818_0900` snapshot supplied only the missing
`evt_O102` invoice-finalization and `evt_C302` retry-schedule records. All
other events came from the local spool, were replayed by provider sequence,
and the duplicate `evt_C303` delivery was counted once. `evt_X901` names no
known subscription and was quarantined without creating a customer record.

Orchid is active on seven Pro seats. Its 2,500-cent partial refund changes the
invoice to partially refunded but does not reduce entitlement. Cobalt's later
verified 9,000-cent payment supersedes the failed attempt and restores four
Team seats. Amber's full 20,000-cent lost chargeback is beyond the published
grace deadline, so the local entitlement is suspended pending manual billing
review. Dahlia remains active on two Basic seats until the scheduled period
end; cancellation was not applied early.

The controller restored the interrupted prior journal before atomically
committing this projection. Preview, verification, local pending-review
receipt, and replay close over the same source, plan, and semantic database
hashes; replay reported byte-stable receipt and semantic state.

No refund, provider cancellation, provider entitlement mutation, customer
notification, or customer contact was executed. The staged receipt is local
review evidence only and does not authorize an external action.
""",
            encoding="utf-8",
        )
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        REFERENCE.mkdir(parents=True)
        for name in (
            "recovery_plan.json", ".entitlement_preview.json", "recovery_handoff.md",
            "state/billing.db", "state/verification.json", "state/recovery_receipt.json",
            "state/replay_report.json",
        ):
            destination = REFERENCE / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / name, destination)


if __name__ == "__main__":
    generate_inputs()
    generate_reference()
