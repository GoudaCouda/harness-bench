#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def original(message_id: str, thread: str, recipient: str, subject: str) -> bytes:
    return (
        "From: operations@example.test\r\n"
        f"To: {recipient}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"X-Thread-ID: {thread}\r\n"
        f"Subject: {subject}\r\n"
        "Date: Tue, 18 Aug 2026 09:00:00 +0000\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "This is an offline fixture message.\r\n"
    ).encode("utf-8")


def dsn(
    dsn_id: str,
    original_id: str,
    recipient: str,
    action: str,
    status: str,
    diagnostic: str,
) -> bytes:
    boundary = "dsn-boundary-" + dsn_id.strip("<>").replace("@", "-")
    return (
        "From: mailer-daemon@example.test\r\n"
        "To: operations@example.test\r\n"
        f"Message-ID: <{dsn_id}@dsn.local>\r\n"
        f"X-DSN-ID: {dsn_id}\r\n"
        "Subject: Delivery Status Notification\r\n"
        "MIME-Version: 1.0\r\n"
        f"Content-Type: multipart/report; report-type=delivery-status; boundary=\"{boundary}\"\r\n"
        "\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n\r\n"
        "Delivery report follows.\r\n"
        f"--{boundary}\r\n"
        "Content-Type: message/delivery-status\r\n\r\n"
        "Reporting-MTA: dns; mx.example.test\r\n\r\n"
        f"Original-Message-ID: {original_id}\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\n"
        f"Action: {action}\r\n"
        f"Status: {status}\r\n"
        f"Diagnostic-Code: smtp; {diagnostic}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")


def create_db(path: Path, clean: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE message_state(
              message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL,
              recipient TEXT NOT NULL, delivery_state TEXT NOT NULL,
              last_dsn_id TEXT, action TEXT NOT NULL, draft_id TEXT
            );
            CREATE TABLE drafts(
              draft_id TEXT PRIMARY KEY, in_reply_to TEXT NOT NULL,
              recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
              status TEXT NOT NULL, approval_id TEXT
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY, checkpoint_id TEXT NOT NULL,
              semantic_sha TEXT NOT NULL, status TEXT NOT NULL, committed_at TEXT NOT NULL
            );
            CREATE TABLE recovery_journal(
              tx_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL,
              status TEXT NOT NULL, before_json TEXT NOT NULL
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany(
            "INSERT INTO message_state VALUES (:message_id,:thread_id,:recipient,:delivery_state,:last_dsn_id,:action,:draft_id)",
            clean["message_state"],
        )
        connection.executemany(
            "INSERT INTO drafts VALUES (:draft_id,:in_reply_to,:recipient,:subject,:body,:status,:approval_id)",
            clean["drafts"],
        )
        connection.execute(
            "INSERT INTO system_state VALUES(?,?)", ("mailbox_checkpoint", "mailbox-20260818-0915")
        )
        before = canonical(clean).decode("utf-8")
        connection.execute(
            "INSERT INTO recovery_journal VALUES(?,?,?,?)",
            ("tx-interrupted-41", "prior-crash", "prepared", before),
        )
        connection.execute(
            "UPDATE message_state SET delivery_state='hard_bounced',action='partial_crash_write' WHERE message_id='<shipment-c@ops.local>'"
        )
        connection.execute("DELETE FROM drafts WHERE draft_id='draft-pending-d'")


def build() -> None:
    shutil.rmtree(WORKSPACE / "__pycache__", ignore_errors=True)
    for relative in ("maildir/cur", "evidence", "policy", "state"):
        (WORKSPACE / relative).mkdir(parents=True, exist_ok=True)
    mail = {
        "1001.eml": original(
            "<invoice-a@ops.local>", "thread-invoice-a", "billing-a@example.test", "Invoice receipt A"
        ),
        "1001-copy.eml": original(
            "<invoice-a@ops.local>", "thread-invoice-a", "billing-a@example.test", "Invoice receipt A"
        ),
        "1002.eml": original(
            "<notice-b@ops.local>", "thread-notice-b", "old-b@example.test", "Compliance notice B"
        ),
        "1003.eml": original(
            "<shipment-c@ops.local>", "thread-shipment-c", "dock-c@example.test", "Shipment update C"
        ),
        "1004.eml": original(
            "<renewal-d@ops.local>", "thread-renewal-d", "owner-d@example.test", "Renewal reminder D"
        ),
    }
    delivered = dsn(
        "dsn-delivered-a", "<invoice-a@ops.local>", "billing-a@example.test", "delivered", "2.0.0", "250 accepted"
    )
    mail.update(
        {
            "2001.eml": delivered,
            "2001-copy.eml": delivered,
            "2002.eml": dsn(
                "dsn-failed-b", "<notice-b@ops.local>", "old-b@example.test", "failed", "5.1.1", "550 mailbox unavailable"
            ),
            "2003.eml": dsn(
                "dsn-delayed-c", "<shipment-c@ops.local>", "dock-c@example.test", "delayed", "4.2.0", "450 retry scheduled"
            ),
            "2004.eml": dsn(
                "dsn-mismatch-d", "<renewal-d@ops.local>", "other@example.test", "failed", "5.1.1", "550 recipient mismatch"
            ),
            "2099.eml": dsn(
                "dsn-orphan-z", "<unknown-z@ops.local>", "nobody@example.test", "failed", "5.1.1", "550 unknown"
            ),
        }
    )
    for name, raw in mail.items():
        (WORKSPACE / "maildir/cur" / name).write_bytes(raw)

    trust = {
        "schema_version": 1,
        "keys": [
            {"key_id": "mail-approver-2026", "status": "active", "verification_material": "offline-mail-approval-material-v1"},
            {"key_id": "retired-key", "status": "retired", "verification_material": "retired-material"},
        ],
    }
    valid = {
        "approval_id": "approval-b-77",
        "key_id": "mail-approver-2026",
        "decision": "approve_redraft",
        "original_message_id": "<notice-b@ops.local>",
        "corrected_recipient": "compliance-b@example.test",
        "approved_at": "2026-08-18T09:20:00Z",
    }
    valid["signature"] = digest(
        canonical(valid) + b"offline-mail-approval-material-v1"
    )
    invalid = {
        "approval_id": "approval-d-untrusted",
        "key_id": "retired-key",
        "decision": "approve_redraft",
        "original_message_id": "<renewal-d@ops.local>",
        "corrected_recipient": "attacker@example.test",
        "approved_at": "2026-08-18T09:21:00Z",
        "signature": "not-a-valid-signature",
    }
    write_json(WORKSPACE / "evidence/approval_trust.json", trust)
    write_json(WORKSPACE / "evidence/approvals.json", {"schema_version": 1, "approvals": [invalid, valid]})
    write_json(
        WORKSPACE / "evidence/mailbox_checkpoint.json",
        {"schema_version": 1, "checkpoint_id": "mailbox-20260818-0915", "captured_at": "2026-08-18T09:15:00Z"},
    )
    write_json(
        WORKSPACE / "policy/recovery_policy.json",
        {
            "schema_version": 1,
            "recovery_id": "mail-recovery-20260818-42",
            "as_of": "2026-08-18T09:30:00Z",
            "delivery_state_vocabulary": [
                "delivered", "hard_bounced", "delayed", "pending"
            ],
            "action_vocabulary": [
                "close_delivery", "stage_approved_redraft",
                "hold_bounce_without_approval", "monitor_delivery",
                "preserve_pending"
            ],
            "delivery_actions": {
                "usable_delivered_dsn": {
                    "delivery_state": "delivered", "action": "close_delivery"
                },
                "usable_failed_dsn_with_verified_approval": {
                    "delivery_state": "hard_bounced",
                    "action": "stage_approved_redraft"
                },
                "usable_failed_dsn_without_verified_approval": {
                    "delivery_state": "hard_bounced",
                    "action": "hold_bounce_without_approval"
                },
                "usable_delayed_dsn": {
                    "delivery_state": "delayed", "action": "monitor_delivery"
                },
                "no_usable_dsn": {
                    "delivery_state": "pending", "action": "preserve_pending"
                }
            },
            "external_send_authorized": False,
        },
    )
    clean = {
        "message_state": [
            {"message_id": "<invoice-a@ops.local>", "thread_id": "thread-invoice-a", "recipient": "billing-a@example.test", "delivery_state": "sent", "last_dsn_id": None, "action": "unreconciled", "draft_id": "draft-stale-a"},
            {"message_id": "<notice-b@ops.local>", "thread_id": "thread-notice-b", "recipient": "old-b@example.test", "delivery_state": "sent", "last_dsn_id": None, "action": "unreconciled", "draft_id": None},
            {"message_id": "<shipment-c@ops.local>", "thread_id": "thread-shipment-c", "recipient": "dock-c@example.test", "delivery_state": "sent", "last_dsn_id": None, "action": "unreconciled", "draft_id": None},
            {"message_id": "<renewal-d@ops.local>", "thread_id": "thread-renewal-d", "recipient": "owner-d@example.test", "delivery_state": "sent", "last_dsn_id": None, "action": "unreconciled", "draft_id": "draft-pending-d"},
        ],
        "drafts": [
            {"draft_id": "draft-stale-a", "in_reply_to": "<invoice-a@ops.local>", "recipient": "billing-a@example.test", "subject": "RETRY: Invoice receipt A", "body": "Stale retry that must be removed after delivered DSN.", "status": "stale", "approval_id": None},
            {"draft_id": "draft-pending-d", "in_reply_to": "<renewal-d@ops.local>", "recipient": "owner-d@example.test", "subject": "DRAFT: Renewal reminder D", "body": "Pending local draft; preserve until a valid DSN exists.", "status": "pending_review", "approval_id": None},
        ],
    }
    write_json(WORKSPACE / "evidence/initial_local_state.json", clean)
    create_db(WORKSPACE / "state/mailops.db", clean)

    protected = [
        path
        for path in WORKSPACE.rglob("*")
        if path.is_file()
        and path.relative_to(WORKSPACE).as_posix()
        not in {"SOURCE_HASHES.json", "state/mailops.db"}
    ]
    write_json(
        WORKSPACE / "SOURCE_HASHES.json",
        {
            "schema_version": 1,
            "sha256": {
                path.relative_to(WORKSPACE).as_posix(): digest(path.read_bytes())
                for path in sorted(protected)
            },
        },
    )

    plan = {
        "schema_version": 1,
        "recovery_id": "mail-recovery-20260818-42",
        "mailbox_checkpoint": "mailbox-20260818-0915",
        "decisions": [
            {
                "message_id": "<invoice-a@ops.local>",
                "thread_id": "thread-invoice-a",
                "delivery_state": "delivered",
                "dsn_ids": ["dsn-delivered-a"],
                "action": "close_delivery",
                "target_recipient": "billing-a@example.test",
                "approval_id": None,
                "draft_id": None,
                "evidence_refs": [
                    "maildir/cur/1001.eml", "maildir/cur/1001-copy.eml",
                    "maildir/cur/2001.eml", "maildir/cur/2001-copy.eml"
                ],
            },
            {
                "message_id": "<notice-b@ops.local>",
                "thread_id": "thread-notice-b",
                "delivery_state": "hard_bounced",
                "dsn_ids": ["dsn-failed-b"],
                "action": "stage_approved_redraft",
                "target_recipient": "compliance-b@example.test",
                "approval_id": "approval-b-77",
                "draft_id": "draft-898f9fc9c139",
                "evidence_refs": [
                    "maildir/cur/1002.eml", "maildir/cur/2002.eml",
                    "evidence/approvals.json#approval-b-77"
                ],
            },
            {
                "message_id": "<shipment-c@ops.local>",
                "thread_id": "thread-shipment-c",
                "delivery_state": "delayed",
                "dsn_ids": ["dsn-delayed-c"],
                "action": "monitor_delivery",
                "target_recipient": "dock-c@example.test",
                "approval_id": None,
                "draft_id": None,
                "evidence_refs": ["maildir/cur/1003.eml", "maildir/cur/2003.eml"],
            },
            {
                "message_id": "<renewal-d@ops.local>",
                "thread_id": "thread-renewal-d",
                "delivery_state": "pending",
                "dsn_ids": [],
                "action": "preserve_pending",
                "target_recipient": "owner-d@example.test",
                "approval_id": None,
                "draft_id": None,
                "evidence_refs": ["maildir/cur/1004.eml"],
            },
        ],
        "quarantined_dsn_ids": ["dsn-mismatch-d", "dsn-orphan-z"],
        "ignored_approval_ids": ["approval-d-untrusted"],
        "external_messages_sent": False,
    }

    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, candidate)
        write_json(candidate / "recovery_plan.json", plan)
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", "mailctl.py", command, "recovery_plan.json"],
                cwd=candidate,
                check=True,
                capture_output=True,
                text=True,
            )
        write_json(REFERENCE / "recovery_plan.json", plan)
        for relative in (
            ".mail_preview.json",
            "state/mailops.db",
            "state/verification.json",
            "state/stage_receipt.json",
            "state/replay_report.json",
        ):
            destination = REFERENCE / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate / relative, destination)
    (REFERENCE / "recovery_handoff.md").write_text(
        """# Offline mailbox DSN recovery handoff

The Maildir identity graph was reconciled by original `Message-ID`, not filename or copy order. The delivered invoice DSN closed its stale retry draft; the hard bounce was linked to the signed approval and produced one corrected-recipient draft pending human review. The delayed shipment remains under monitoring, while the renewal remains pending because its recipient-mismatched DSN was quarantined.

The duplicate delivered DSN was deduplicated. The orphan and mismatched DSNs were quarantined, and the retired-key approval was ignored. The prepared SQLite journal was rolled back before the new transaction committed. Verification passed, and an equivalent replay left the database and staged receipt byte-stable.

No message was sent, resent, forwarded, deleted from the source Maildir, or otherwise executed externally. The replacement remains a local draft for human review.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
