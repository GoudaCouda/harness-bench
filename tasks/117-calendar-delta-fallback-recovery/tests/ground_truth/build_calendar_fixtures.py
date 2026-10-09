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
DB = WORKSPACE / "state/calendar.db"
NOW = "2026-08-19T12:15:00Z"
RECOVERY_ID = "CALSYNC-FINANCE-20260819-42"
SOURCE_CHECKPOINT = "62db0a06d68abb552e70b31b490a149a4ef84b608da6baf629690e64efd0bfbf"


def event(
    uid: str, recurrence_id: str, start: str, end: str, tzid: str,
    summary: str, sequence: int, etag: str, *, rrule: str = "",
) -> dict[str, object]:
    return {
        "uid": uid, "recurrence_id": recurrence_id, "dtstart_utc": start,
        "dtend_utc": end, "tzid": tzid, "summary": summary,
        "status": "CONFIRMED", "rrule": rrule, "sequence": sequence,
        "source_etag": etag,
    }


def create_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        CREATE TABLE events(
          uid TEXT NOT NULL, recurrence_id TEXT NOT NULL DEFAULT '',
          dtstart_utc TEXT NOT NULL, dtend_utc TEXT NOT NULL, tzid TEXT NOT NULL,
          summary TEXT NOT NULL, status TEXT NOT NULL, rrule TEXT NOT NULL,
          sequence INTEGER NOT NULL, source_etag TEXT NOT NULL,
          PRIMARY KEY(uid, recurrence_id)
        );
        CREATE TABLE tombstones(
          uid TEXT NOT NULL, recurrence_id TEXT NOT NULL DEFAULT '',
          sequence INTEGER NOT NULL, source_etag TEXT NOT NULL,
          PRIMARY KEY(uid, recurrence_id)
        );
        CREATE TABLE sync_checkpoint(
          collection_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL,
          cursor TEXT NOT NULL, collection_etag TEXT NOT NULL,
          source_checkpoint TEXT NOT NULL, phase TEXT NOT NULL
        );
        CREATE TABLE sync_ledger(
          component_id TEXT PRIMARY KEY, disposition TEXT NOT NULL,
          source_page TEXT NOT NULL, sequence INTEGER NOT NULL,
          source_etag TEXT NOT NULL, applied_at TEXT NOT NULL
        );
        CREATE TABLE sync_journal(
          recovery_id TEXT PRIMARY KEY, phase TEXT NOT NULL,
          source_checkpoint TEXT NOT NULL, plan_sha256 TEXT NOT NULL,
          prepared_page TEXT NOT NULL, recovered_from_interrupt INTEGER NOT NULL,
          committed_at TEXT
        );
        CREATE TABLE rollback_rows(
          table_name TEXT NOT NULL, record_key TEXT PRIMARY KEY,
          before_json TEXT NOT NULL, restored INTEGER NOT NULL
        );
        CREATE TABLE recovery_transactions(
          recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL,
          plan_sha256 TEXT NOT NULL, semantic_state_sha256 TEXT NOT NULL,
          action_count INTEGER NOT NULL, committed_at TEXT NOT NULL
        );
        """
    )
    old_master = event(
        "ops-rotation@example.test", "", "2026-08-18T13:00:00Z",
        "2026-08-18T14:00:00Z", "America/New_York", "Ops rotation",
        1, 'W/"cal-41"', rrule="FREQ=DAILY;COUNT=5",
    )
    partial_master = dict(old_master)
    partial_master.update({
        "dtstart_utc": "2026-08-18T13:30:00Z", "dtend_utc": "2026-08-18T14:30:00Z",
        "summary": "Operations rotation - partial write", "sequence": 2,
        "source_etag": 'W/"cal-42a"',
    })
    rows = [
        partial_master,
        event("ops-rotation@example.test", "20260819T090000", "2026-08-19T13:00:00Z", "2026-08-19T14:00:00Z", "America/New_York", "Rotation", 1, 'W/"cal-41"'),
        event("budget-close@example.test", "", "2026-08-22T16:00:00Z", "2026-08-22T17:00:00Z", "UTC", "Budget close", 3, 'W/"cal-41"'),
        event("obsolete-briefing@example.test", "", "2026-08-23T15:00:00Z", "2026-08-23T15:30:00Z", "UTC", "Obsolete briefing", 1, 'W/"cal-41"'),
        event("townhall@example.test", "", "2026-08-25T17:00:00Z", "2026-08-25T18:00:00Z", "America/Los_Angeles", "Company town hall", 2, 'W/"cal-41"'),
        event("legal-hold@example.test", "", "2026-09-01T16:00:00Z", "2026-09-01T17:00:00Z", "America/New_York", "Protected legal hold review", 7, 'W/"protected"'),
    ]
    for row in rows:
        connection.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(row[key] for key in (
                "uid", "recurrence_id", "dtstart_utc", "dtend_utc", "tzid",
                "summary", "status", "rrule", "sequence", "source_etag",
            )),
        )
    connection.execute(
        "INSERT INTO sync_checkpoint VALUES (?, ?, ?, ?, ?, ?)",
        ("finance-operations", RECOVERY_ID, "cursor-41", 'W/"cal-41"', SOURCE_CHECKPOINT, "prepared"),
    )
    connection.execute(
        "INSERT INTO sync_journal VALUES (?, 'prepared', ?, '', 'page1', 0, NULL)",
        (RECOVERY_ID, SOURCE_CHECKPOINT),
    )
    connection.execute(
        "INSERT INTO rollback_rows VALUES ('events', ?, ?, 0)",
        ("ops-rotation@example.test|master", json.dumps(old_master, sort_keys=True, separators=(",", ":"))),
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def plan() -> dict[str, object]:
    actions = [
        ("ops-rotation@example.test|master", "upsert_master", "page1"),
        ("ops-rotation@example.test|20260819T090000", "upsert_override", "page1"),
        ("ops-rotation@example.test|20260820T090000", "cancel_occurrence", "page1"),
        ("budget-close@example.test|master", "upsert_event", "page1"),
        ("obsolete-briefing@example.test|master", "tombstone_event", "page1"),
        ("ops-rotation@example.test|20260821T090000", "upsert_override", "page2"),
        ("london-review@example.test|master", "insert_event", "page2"),
        ("townhall@example.test|master", "ignore_stale", "page2"),
    ]
    rows = []
    for identity, disposition, page in actions:
        source = "evidence/page1.ics" if page == "page1" else "evidence/page2_recovery.ics"
        refs = [f"{source}#{identity}", f"policy/sync_manifest.json#pages.{page}"]
        rows.append({"component_id": identity, "disposition": disposition, "evidence_refs": refs})
    return {
        "schema_version": 1,
        "recovery_id": RECOVERY_ID,
        "collection_id": "finance-operations",
        "source_checkpoint": SOURCE_CHECKPOINT,
        "fallback": {
            "damaged_page": "evidence/page2.part",
            "selected_page": "evidence/page2_recovery.ics",
            "selected_sha256": "485b5c31558285c394443ac8f274d8194fc16195a23b182293f60ab56ea3bed3",
            "expected_etag": 'W/"cal-42b"',
            "reason": "The cached page is truncated and its checksum does not equal the authorized fallback checksum.",
        },
        "actions": rows,
        "external_calendar_write_executed": False,
    }


def write_source_hashes() -> None:
    paths = [
        "evidence/page1.ics", "evidence/page2.part", "evidence/page2_recovery.ics",
        "policy/recovery_policy.md", "policy/sync_manifest.json", "policy/timezone_registry.json",
        "syncctl.py",
    ]
    hashes = {name: hashlib.sha256((WORKSPACE / name).read_bytes()).hexdigest() for name in paths}
    (WORKSPACE / "SOURCE_HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")


def build_reference() -> None:
    shutil.rmtree(REFERENCE, ignore_errors=True)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hb117-reference-") as directory:
        target = Path(directory) / "workspace"
        shutil.copytree(WORKSPACE, target)
        (target / "recovery_plan.json").write_text(json.dumps(plan(), indent=2) + "\n")
        handoff = """# Calendar sync recovery handoff

Recovery `CALSYNC-FINANCE-20260819-42` remained offline. I rejected the truncated `page2.part` after its parse failure and checksum mismatch, then selected `page2_recovery.ics` because its SHA-256 and the page-1-to-page-2 ETag chain matched the manifest.

The prepared page-1 journal was rolled back and the complete two-page chain was applied atomically. The `ops-rotation@example.test` master advanced independently from its RFC 5545 `RECURRENCE-ID` instances: the August 19 instance moved, August 20 became a cancellation tombstone, and the August 21 override crosses from an America/New_York recurrence identity to a Europe/London start. The timezone conversion resolves the latter to 15:00Z, while the new London review resolves to 13:00Z. The budget event advanced, the obsolete standalone event became a tombstone, and the lower-SEQUENCE town-hall copy was ignored as stale. The protected legal-hold row was preserved.

The stable recovery identity and immutable source checkpoint own one committed SQLite transaction. Preview passed, verification reconciled component, tombstone, ledger, cursor `cursor-42b`, and ETag `W/\"cal-42b\"` state, and staging created only a pending owner-review receipt. Replay returned an idempotent no-op with the same semantic database digest. No remote calendar write, invitation, cancellation notice, attendee message, or other external action occurred.
"""
        (target / "recovery_handoff.md").write_text(handoff)
        for command in (
            ("preview", "recovery_plan.json"), ("apply", "recovery_plan.json"),
            ("verify",), ("stage", "recovery_plan.json"), ("replay", "recovery_plan.json"),
        ):
            subprocess.run(["python3", "syncctl.py", *command], cwd=target, check=True, stdout=subprocess.DEVNULL)
        for name in ("recovery_plan.json", ".calendar_preview.json", "recovery_handoff.md"):
            shutil.copy2(target / name, REFERENCE / name)
        (REFERENCE / "state").mkdir()
        for name in ("calendar.db", "calendar_verification.json", "recovery_receipt.json", "replay_report.json"):
            shutil.copy2(target / "state" / name, REFERENCE / "state" / name)


def main() -> None:
    create_database(DB)
    write_source_hashes()
    build_reference()
    print("rebuilt task 117 fixtures and reference")


if __name__ == "__main__":
    main()
