#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
sys.dont_write_bytecode = True


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def reset_dirs() -> None:
    for path in (WORKSPACE / "policy", WORKSPACE / "evidence", WORKSPACE / "state", REFERENCE):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True)


def write_sources() -> None:
    policy = {
        "schema_version": 1,
        "recovery_id": "MBR-202611-FALLBACK-01",
        "billing_cycle": "2026-11",
        "timezone": "America/New_York",
        "energy_rounding_decimals": 3,
        "correction_states": ["correction_pending_review", "hold_insufficient_evidence"],
        "authority_methods": [
            "interval_utc_deduplicated",
            "register_rollover",
            "bidirectional_interval",
            "signed_fallback_snapshot",
            "insufficient_evidence",
        ],
        "meters": [
            {"account_id": "ACCT-DST-17", "meter_id": "MTR-DST-17", "authority_method": "interval_utc_deduplicated", "expected_interval_count": 4},
            {"account_id": "ACCT-ROL-42", "meter_id": "MTR-ROL-42", "authority_method": "register_rollover"},
            {"account_id": "ACCT-SOL-09", "meter_id": "MTR-SOL-09", "authority_method": "bidirectional_interval", "expected_interval_count": 4},
            {"account_id": "ACCT-FBK-88", "meter_id": "MTR-FBK-88", "authority_method": "signed_fallback_snapshot"},
            {"account_id": "ACCT-HLD-55", "meter_id": "MTR-HLD-55", "authority_method": "insufficient_evidence", "minimum_complete_intervals": 4},
        ],
        "external_actions_prohibited": ["issue_bill", "post_refund", "take_payment", "send_meter_command", "contact_customer"],
    }
    write_json(WORKSPACE / "policy/billing_policy.json", policy)
    events = [
        {"event_id": "EVT-SOL-03", "sequence": 1, "meter_id": "MTR-SOL-09", "cycle": "2026-11", "interval_start_utc": "2026-11-01T07:30:00Z", "local_start": "2026-11-01T02:30:00", "utc_offset": "-05:00", "import_kwh": 2.0, "export_kwh": 0.5, "quality": "actual"},
        {"event_id": "EVT-DST-02", "sequence": 4, "meter_id": "MTR-DST-17", "cycle": "2026-11", "interval_start_utc": "2026-11-01T05:30:00Z", "local_start": "2026-11-01T01:30:00", "utc_offset": "-04:00", "import_kwh": 1.2, "export_kwh": 0.0, "quality": "actual"},
        {"event_id": "EVT-HLD-01", "sequence": 1, "meter_id": "MTR-HLD-55", "cycle": "2026-11", "interval_start_utc": "2026-11-01T05:00:00Z", "local_start": "2026-11-01T01:00:00", "utc_offset": "-04:00", "import_kwh": 1.1, "export_kwh": 0.0, "quality": "actual"},
        {"event_id": "EVT-DST-04", "sequence": 1, "meter_id": "MTR-DST-17", "cycle": "2026-11", "interval_start_utc": "2026-11-01T07:00:00Z", "local_start": "2026-11-01T02:00:00", "utc_offset": "-05:00", "import_kwh": 0.8, "export_kwh": 0.0, "quality": "actual"},
        {"event_id": "EVT-SOL-01", "sequence": 1, "meter_id": "MTR-SOL-09", "cycle": "2026-11", "interval_start_utc": "2026-11-01T05:30:00Z", "local_start": "2026-11-01T01:30:00", "utc_offset": "-04:00", "import_kwh": 1.5, "export_kwh": 1.0, "quality": "actual"},
        {"event_id": "EVT-DST-01", "sequence": 1, "meter_id": "MTR-DST-17", "cycle": "2026-11", "interval_start_utc": "2026-11-01T05:00:00Z", "local_start": "2026-11-01T01:00:00", "utc_offset": "-04:00", "import_kwh": 1.0, "export_kwh": 0.0, "quality": "actual"},
        {"event_id": "EVT-DST-03", "sequence": 1, "meter_id": "MTR-DST-17", "cycle": "2026-11", "interval_start_utc": "2026-11-01T06:30:00Z", "local_start": "2026-11-01T01:30:00", "utc_offset": "-05:00", "import_kwh": 1.5, "export_kwh": 0.0, "quality": "actual"},
        {"event_id": "EVT-DST-02", "sequence": 2, "meter_id": "MTR-DST-17", "cycle": "2026-11", "interval_start_utc": "2026-11-01T05:30:00Z", "local_start": "2026-11-01T01:30:00", "utc_offset": "-04:00", "import_kwh": 1.2, "export_kwh": 0.0, "quality": "actual"},
        {"event_id": "EVT-SOL-04", "sequence": 1, "meter_id": "MTR-SOL-09", "cycle": "2026-11", "interval_start_utc": "2026-11-01T08:00:00Z", "local_start": "2026-11-01T03:00:00", "utc_offset": "-05:00", "import_kwh": 1.8, "export_kwh": 0.7, "quality": "actual"},
        {"event_id": "EVT-HLD-02", "sequence": 1, "meter_id": "MTR-HLD-55", "cycle": "2026-11", "interval_start_utc": "2026-11-01T05:30:00Z", "local_start": "2026-11-01T01:30:00", "utc_offset": "-04:00", "import_kwh": 1.0, "export_kwh": 0.0, "quality": "estimated"},
        {"event_id": "EVT-SOL-02", "sequence": 1, "meter_id": "MTR-SOL-09", "cycle": "2026-11", "interval_start_utc": "2026-11-01T06:30:00Z", "local_start": "2026-11-01T01:30:00", "utc_offset": "-05:00", "import_kwh": 2.2, "export_kwh": 0.8, "quality": "actual"},
    ]
    (WORKSPACE / "evidence/interval_feed.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in events), encoding="utf-8"
    )
    with (WORKSPACE / "evidence/register_reads.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["read_id", "meter_id", "cycle", "start_register", "end_register", "modulus", "quality"])
        writer.writeheader()
        writer.writerow({"read_id": "REG-ROL-START-END", "meter_id": "MTR-ROL-42", "cycle": "2026-11", "start_register": "9998", "end_register": "4", "modulus": "10000", "quality": "actual"})
    (WORKSPACE / "evidence/primary_batch.json.part").write_text(
        '{"batch_id":"PRIMARY-202611","records":[{"meter_id":"MTR-FBK-88",', encoding="utf-8"
    )
    trust = {"schema_version": 1, "key_id": "meter-batch-key-2026", "verification_material": "synthetic-offline-meter-batch-verifier-v1"}
    write_json(WORKSPACE / "evidence/fallback_trust.json", trust)
    payload = {
        "schema_version": 1,
        "batch_id": "FALLBACK-202611-RECOVERY-A",
        "records": [{"record_id": "FBK-REC-88", "account_id": "ACCT-FBK-88", "meter_id": "MTR-FBK-88", "cycle": "2026-11", "import_kwh": 12.4, "export_kwh": 0.0, "quality": "validated_actual"}],
    }
    fallback = {
        **payload,
        "key_id": trust["key_id"],
        "payload_checksum": digest(canonical(payload)),
        "signature": digest(canonical(payload) + trust["verification_material"].encode()),
    }
    write_json(WORKSPACE / "evidence/fallback_batch.json", fallback)


def make_database() -> None:
    path = WORKSPACE / "state/billing.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE bills (
                account_id TEXT NOT NULL,
                meter_id TEXT PRIMARY KEY,
                cycle TEXT NOT NULL,
                billed_import_kwh REAL NOT NULL,
                billed_export_kwh REAL NOT NULL,
                corrected_import_kwh REAL,
                corrected_export_kwh REAL,
                billing_state TEXT NOT NULL,
                prospective_balance_delta_cents INTEGER NOT NULL,
                rate_cents_per_kwh INTEGER NOT NULL,
                invoice_state TEXT NOT NULL,
                version INTEGER NOT NULL
            );
            CREATE TABLE correction_runs (
                recovery_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                source_checkpoint TEXT NOT NULL,
                semantic_plan_digest TEXT NOT NULL,
                semantic_db_digest TEXT NOT NULL,
                final_revision INTEGER NOT NULL,
                external_actions_executed INTEGER NOT NULL,
                customer_contacted INTEGER NOT NULL
            );
            CREATE TABLE correction_journal (
                journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recovery_id TEXT NOT NULL,
                meter_id TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                restored INTEGER NOT NULL
            );
            CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        bills = [
            ("ACCT-DST-17", "MTR-DST-17", 3.8, 0.0, 21),
            ("ACCT-FBK-88", "MTR-FBK-88", 11.0, 0.0, 19),
            ("ACCT-HLD-55", "MTR-HLD-55", 5.0, 0.0, 20),
            ("ACCT-ROL-42", "MTR-ROL-42", 10.0, 0.0, 18),
            ("ACCT-SOL-09", "MTR-SOL-09", 8.0, 0.0, 24),
        ]
        for account, meter, imported, exported, rate in bills:
            connection.execute(
                "INSERT INTO bills VALUES (?,?,?,?,?,NULL,NULL,'estimated',0,?,'estimated_unissued',7)",
                (account, meter, "2026-11", imported, exported, rate),
            )
        cursor = connection.execute("SELECT * FROM bills WHERE meter_id='MTR-DST-17'")
        columns = [item[0] for item in cursor.description]
        before = dict(zip(columns, cursor.fetchone(), strict=True))
        connection.execute(
            "UPDATE bills SET corrected_import_kwh=4.5,billing_state='partial_reversal',prospective_balance_delta_cents=15,version=8 WHERE meter_id='MTR-DST-17'"
        )
        cursor = connection.execute("SELECT * FROM bills WHERE meter_id='MTR-DST-17'")
        after = dict(zip(columns, cursor.fetchone(), strict=True))
        connection.execute(
            "INSERT INTO correction_runs VALUES (?,?,?,?,?,?,0,0)",
            ("MBR-INTERRUPTED-20261116", "interrupted", "legacy-checkpoint", "legacy-plan", "legacy-db", 74),
        )
        connection.execute(
            "INSERT INTO correction_journal (recovery_id,meter_id,before_json,after_json,restored) VALUES (?,?,?,?,0)",
            ("MBR-INTERRUPTED-20261116", "MTR-DST-17", canonical(before).decode().strip(), canonical(after).decode().strip()),
        )
        connection.executemany(
            "INSERT INTO system_state VALUES (?,?)",
            [("billing_revision", "73"), ("source_billing_revision", "73"), ("stage_state", "interrupted")],
        )
        connection.commit()


def write_manifest() -> None:
    locators = [
        "meterctl.py",
        "policy/billing_policy.json",
        "evidence/interval_feed.jsonl",
        "evidence/register_reads.csv",
        "evidence/primary_batch.json.part",
        "evidence/fallback_trust.json",
        "evidence/fallback_batch.json",
    ]
    write_json(
        WORKSPACE / "policy/source_manifest.json",
        {"schema_version": 1, "files": {locator: digest((WORKSPACE / locator).read_bytes()) for locator in locators}},
    )


def build_reference() -> None:
    spec = importlib.util.spec_from_file_location(
        "meter_outcome_fixture", TASK / "tests/test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load meter controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    facts = module._truth()
    write_json(WORKSPACE / "correction_plan.json", facts["plan"])
    handoff = """# Smart-meter correction recovery handoff

## Authority and interval resolution

The raw interval feed arrived out of order and retransmitted `EVT-DST-02`.
Event identity was deduplicated without treating local clock time as identity.
For `MTR-DST-17`, both 01:30 readings were retained: one carries UTC offset
-04:00 and the other -05:00, so they are distinct fall-back intervals. Their UTC
starts and the other actual intervals support 4.500 kWh import. `MTR-ROL-42`
crossed a 10000 register modulus from 9998 to 4; the authoritative consumption
is therefore 6.000 kWh, not a negative delta or 9994 kWh.

`MTR-SOL-09` was resolved from four actual bidirectional intervals. Import totals
7.500 kWh and export totals 3.000 kWh; export was not netted away before the
billing comparison. The primary batch for `MTR-FBK-88` is truncated and was
rejected. Its local fallback record was accepted only after both its canonical
payload checksum and the signature bound to `meter-batch-key-2026` verified,
yielding 12.400 kWh import and zero export.

## Hold and local recovery

`MTR-HLD-55` remains `hold_insufficient_evidence`: only one actual interval and
one estimated interval are present, below the required coverage. No estimated
quantity was promoted to an actual correction. The other four projections are
`correction_pending_review`; these are proposals for billing review, not issued
bills or balance postings.

The prior `MBR-INTERRUPTED-20261116` partial reversal was restored from its
before-image inside the same SQLite transaction that committed this recovery.
Verification confirmed exact bill projections, one revision advance, the
restored journal, one current journal row per meter, unchanged account/meter
identity, and every invoice still `estimated_unissued`. The recovery was staged
locally, and semantic replay was a database- and receipt-byte-stable no-op.

No bill or refund was issued, no payment was taken, no meter command was sent,
and no customer was contacted. The receipt is pending metering and billing
review only; it does not authorize any external action.
"""
    (WORKSPACE / "meter_recovery_handoff.md").write_text(handoff, encoding="utf-8")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        subprocess.run(
            ["python3", "meterctl.py", command, "correction_plan.json"],
            cwd=WORKSPACE,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    for relative in (
        "correction_plan.json",
        ".meter_preview.json",
        "meter_recovery_handoff.md",
        "state/billing.db",
        "state/verification.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
    ):
        destination = REFERENCE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORKSPACE / relative, destination)
    for relative in (
        "correction_plan.json",
        ".meter_preview.json",
        "meter_recovery_handoff.md",
        "state/verification.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
    ):
        (WORKSPACE / relative).unlink()
    (WORKSPACE / "state/billing.db").unlink()
    make_database()


def main() -> None:
    reset_dirs()
    write_sources()
    make_database()
    write_manifest()
    build_reference()


if __name__ == "__main__":
    main()
