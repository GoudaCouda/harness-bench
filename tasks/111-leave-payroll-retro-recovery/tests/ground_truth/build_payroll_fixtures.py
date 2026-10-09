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
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def reference_plan() -> dict[str, object]:
    return {
        "schema_version": 1,
        "batch_id": "RB-2026-08-A",
        "source_period_id": "PP-2026-07-A",
        "target_period_id": "PP-2026-08-A",
        "strategy": "authoritative_revision_retro",
        "frozen_source_action": "preserve_paid_locked",
        "approval_boundary": "staged_pending_payroll_approval",
        "dispositions": [
            {
                "request_id": "LR-9001",
                "selected_approval_id": "APR-9001-R2",
                "selected_revision": 2,
                "disposition": "stage_retro",
                "reason_code": "authoritative_revision_after_paid_lock",
                "evidence": [
                    "evidence/late_approvals.json#APR-9001-R2",
                    "evidence/approval_keys.json#K-HR-7",
                    "evidence/employees.json#E-101",
                    "policy/retro_policy.json#rule_order",
                    "state/hris_payroll.db#payroll_lines/PL-1001",
                ],
            },
            {
                "request_id": "LR-9002",
                "selected_approval_id": "APR-9002-R3",
                "selected_revision": 3,
                "disposition": "stage_retro",
                "reason_code": "authoritative_revision_after_paid_lock",
                "evidence": [
                    "evidence/late_approvals.json#APR-9002-R3",
                    "evidence/approval_keys.json#K-HR-7",
                    "evidence/employees.json#E-202",
                    "policy/retro_policy.json#rule_order",
                    "state/hris_payroll.db#payroll_lines/PL-1002",
                ],
            },
            {
                "request_id": "LR-9003",
                "selected_approval_id": "APR-9003-R2",
                "selected_revision": 2,
                "disposition": "held_authority",
                "reason_code": "unverified_or_unauthorized_signer",
                "evidence": [
                    "evidence/late_approvals.json#APR-9003-R2",
                    "evidence/approval_keys.json#K-MGR-3",
                    "evidence/employees.json#E-303",
                    "policy/retro_policy.json#rule_order",
                ],
            },
            {
                "request_id": "LR-9004",
                "selected_approval_id": "APR-9004-R2",
                "selected_revision": 2,
                "disposition": "held_eligibility",
                "reason_code": "ineligible_on_local_start_date",
                "evidence": [
                    "evidence/late_approvals.json#APR-9004-R2",
                    "evidence/approval_keys.json#K-HR-7",
                    "evidence/employees.json#E-404",
                    "policy/retro_policy.json#rule_order",
                ],
            },
        ],
        "adjustments": [
            {"adjustment_id": "RA-9001-ADD-SICK-R2", "request_id": "LR-9001", "source_line_id": "PL-1001", "source_revision": 2, "target_period_id": "PP-2026-08-A", "pay_code": "SICK", "hours_delta": 4.0},
            {"adjustment_id": "RA-9001-REV-PTO-R2", "request_id": "LR-9001", "source_line_id": "PL-1001", "source_revision": 2, "target_period_id": "PP-2026-08-A", "pay_code": "PTO", "hours_delta": -8.0},
            {"adjustment_id": "RA-9002-ADD-PFL-R3", "request_id": "LR-9002", "source_line_id": "PL-1002", "source_revision": 3, "target_period_id": "PP-2026-08-A", "pay_code": "PFL", "hours_delta": 8.0},
            {"adjustment_id": "RA-9002-REV-PTO-R3", "request_id": "LR-9002", "source_line_id": "PL-1002", "source_revision": 3, "target_period_id": "PP-2026-08-A", "pay_code": "PTO", "hours_delta": -8.0},
        ],
        "external_actions_executed": False,
    }


def normalized_plan() -> dict[str, object]:
    value = reference_plan()
    value["dispositions"] = sorted(
        (
            {key: item for key, item in row.items() if key != "evidence"}
            for row in value["dispositions"]  # type: ignore[index]
        ),
        key=lambda row: row["request_id"],
    )
    value["adjustments"] = sorted(
        value["adjustments"],  # type: ignore[arg-type]
        key=lambda row: row["adjustment_id"],
    )
    return value


def build_database() -> None:
    target = WORKSPACE / "state/hris_payroll.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    plan_sha = digest(canonical(normalized_plan()))
    db = sqlite3.connect(target)
    db.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA foreign_keys=ON;
        CREATE TABLE payroll_periods (
          period_id TEXT PRIMARY KEY,
          state TEXT NOT NULL,
          period_start TEXT NOT NULL,
          period_end TEXT NOT NULL,
          payment_export_id TEXT,
          locked_at_utc TEXT
        );
        CREATE TABLE payroll_lines (
          line_id TEXT PRIMARY KEY,
          period_id TEXT NOT NULL REFERENCES payroll_periods(period_id),
          employee_id TEXT NOT NULL,
          request_id TEXT,
          revision INTEGER NOT NULL,
          pay_code TEXT NOT NULL,
          hours REAL NOT NULL,
          service_start_local TEXT NOT NULL,
          service_end_local TEXT NOT NULL,
          payment_export_id TEXT NOT NULL
        );
        CREATE TABLE retro_batches (
          batch_id TEXT PRIMARY KEY,
          source_period_id TEXT NOT NULL,
          target_period_id TEXT NOT NULL,
          phase TEXT NOT NULL,
          revision INTEGER NOT NULL,
          plan_sha256 TEXT NOT NULL,
          adjustment_count INTEGER NOT NULL,
          external_payment_executed INTEGER NOT NULL CHECK(external_payment_executed IN (0,1))
        );
        CREATE TABLE retro_adjustments (
          adjustment_id TEXT PRIMARY KEY,
          batch_id TEXT NOT NULL REFERENCES retro_batches(batch_id),
          request_id TEXT NOT NULL,
          source_line_id TEXT NOT NULL REFERENCES payroll_lines(line_id),
          source_revision INTEGER NOT NULL,
          target_period_id TEXT NOT NULL REFERENCES payroll_periods(period_id),
          pay_code TEXT NOT NULL,
          hours_delta REAL NOT NULL,
          status TEXT NOT NULL,
          external_payment_executed INTEGER NOT NULL CHECK(external_payment_executed IN (0,1))
        );
        CREATE TABLE operation_journal (
          sequence INTEGER PRIMARY KEY,
          batch_id TEXT NOT NULL,
          adjustment_id TEXT NOT NULL UNIQUE,
          event TEXT NOT NULL,
          plan_sha256 TEXT NOT NULL,
          recorded_at_utc TEXT NOT NULL
        );
        """
    )
    db.executemany(
        "INSERT INTO payroll_periods VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("PP-2026-07-A", "paid_locked", "2026-07-01", "2026-07-15", "PAYEXP-2026-07-A", "2026-07-17T20:00:00+00:00"),
            ("PP-2026-08-A", "open_for_retro_staging", "2026-08-01", "2026-08-15", None, None),
        ],
    )
    db.executemany(
        "INSERT INTO payroll_lines VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("PL-1001", "PP-2026-07-A", "E-101", "LR-9001", 1, "PTO", 8.0, "2026-07-14T22:00:00-07:00", "2026-07-15T06:00:00-07:00", "PAYEXP-2026-07-A"),
            ("PL-1002", "PP-2026-07-A", "E-202", "LR-9002", 2, "PTO", 8.0, "2026-07-09T09:00:00-04:00", "2026-07-09T17:00:00-04:00", "PAYEXP-2026-07-A"),
            ("PL-1003", "PP-2026-07-A", "E-303", "LR-9003", 1, "PTO", 4.0, "2026-07-11T13:00:00+05:30", "2026-07-11T17:00:00+05:30", "PAYEXP-2026-07-A"),
            ("PL-KEEP", "PP-2026-07-A", "E-777", None, 1, "REG", 80.0, "2026-07-01T00:00:00+00:00", "2026-07-15T23:59:00+00:00", "PAYEXP-2026-07-A"),
        ],
    )
    db.execute(
        "INSERT INTO retro_batches VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("RB-2026-08-A", "PP-2026-07-A", "PP-2026-08-A", "interrupted_after_partial_commit", 1, plan_sha, 1, 0),
    )
    db.execute(
        "INSERT INTO retro_adjustments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("RA-9001-REV-PTO-R2", "RB-2026-08-A", "LR-9001", "PL-1001", 2, "PP-2026-08-A", "PTO", -8.0, "prepared", 0),
    )
    db.execute(
        "INSERT INTO operation_journal VALUES (?, ?, ?, ?, ?, ?)",
        (1, "RB-2026-08-A", "RA-9001-REV-PTO-R2", "committed_before_worker_exit", plan_sha, "2026-08-04T09:12:00+00:00"),
    )
    db.commit()
    db.execute("VACUUM")
    db.close()
    batch = {
        "schema_version": 1,
        "batch_id": "RB-2026-08-A",
        "source_period_id": "PP-2026-07-A",
        "target_period_id": "PP-2026-08-A",
        "phase": "interrupted_after_partial_commit",
        "revision": 1,
        "plan_sha256": plan_sha,
        "adjustment_count": 1,
        "source_payment_export_id": "PAYEXP-2026-07-A",
        "external_payment_executed": False,
    }
    (WORKSPACE / "state/batch.json").write_text(
        json.dumps(batch, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_source_manifest() -> None:
    relative_paths = [
        "payrollctl.py",
        "policy/retro_policy.json",
        "evidence/employees.json",
        "evidence/approval_keys.json",
        "evidence/payroll_calendar.json",
        "evidence/late_approvals.json",
    ]
    manifest = {
        "schema_version": 1,
        "hash_algorithm": "sha256",
        "files": {
            relative: digest((WORKSPACE / relative).read_bytes())
            for relative in relative_paths
        },
    }
    (WORKSPACE / "policy/source_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_reference() -> None:
    shutil.rmtree(REFERENCE, ignore_errors=True)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hb-111-reference-") as directory:
        workspace = Path(directory) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        plan = reference_plan()
        (workspace / "retro_plan.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        handoff = """# Leave/payroll retro recovery handoff

Batch RB-2026-08-A uses the highest signed revisions APR-9001-R2 and
APR-9002-R3 from the active payroll HR director key. LR-9001 is a
cross-midnight America/Los_Angeles interval from 22:00 to 02:00, yielding four
local signed hours rather than a UTC-date grouping. Its paid eight-hour PTO
line is preserved and offset prospectively with a -8 PTO reversal and +4 SICK
entry. LR-9002 is an overlapping same-interval reclassification: the paid
eight-hour PTO line remains immutable while -8 PTO and +8 PFL are staged.

LR-9003 is held because the line-manager credential has schedule-review scope,
not leave-retro authority. LR-9004 is held because its July 15 local start is
before the August 1 eligibility date even though the HR signature is valid.
Neither held request produces a payroll adjustment.

The prior worker's partial-commit checkpoint contained RA-9001-REV-PTO-R2 and
journal sequence 1. The controller reconciled that prefix, appended the other three entries once, and
closed recovery revision 2 without duplicating the reversal. All source-period
rows, PAYEXP-2026-07-A, and unrelated PL-KEEP remain unchanged. The adjustment,
journal, frozen-payroll, semantic-plan, and stage hashes close across SQLite,
.retro_apply_state.json, state/batch.json, and the stage receipt. Repeated
apply, stage, and receipt verification are idempotent.

The batch is only staged into target period PP-2026-08-A with payroll approval
still pending. No payroll was released, no payment was issued, no leave was
approved, and no employee or manager was notified. A payroll approver must
review the local receipt before any external or financial action.
"""
        (workspace / "retro_handoff.md").write_text(handoff, encoding="utf-8")
        for command in (
            ["preview", "--plan", "retro_plan.json"],
            ["apply", "--plan", "retro_plan.json"],
            ["verify", "--plan", "retro_plan.json"],
            ["stage", "--plan", "retro_plan.json"],
            ["verify-stage", "--plan", "retro_plan.json"],
            ["apply", "--plan", "retro_plan.json"],
            ["stage", "--plan", "retro_plan.json"],
        ):
            subprocess.run(
                ["python3", "payrollctl.py", *command], cwd=workspace,
                check=True, text=True, stdout=subprocess.PIPE,
            )
        for relative in (
            "retro_plan.json",
            ".retro_apply_state.json",
            "retro_handoff.md",
            "state/hris_payroll.db",
            "state/batch.json",
            "state/stage_receipt.json",
        ):
            source = workspace / relative
            target = REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def main() -> None:
    build_database()
    build_source_manifest()
    build_reference()


if __name__ == "__main__":
    main()
