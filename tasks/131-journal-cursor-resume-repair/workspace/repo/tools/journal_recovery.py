#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONSUMER = "account-projection"


def records():
    seen_positions = []
    for segment in sorted((ROOT / "journal").glob("segment-*.jsonl")):
        for line_no, raw in enumerate(segment.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{segment.name}:{line_no}: malformed JSON: {exc}")
            required = {"event_id", "account_id", "delta_cents", "occurred_at"}
            if set(event) != required or not isinstance(event["delta_cents"], int):
                raise SystemExit(f"{segment.name}:{line_no}: invalid event shape")
            seen_positions.append((segment.name, line_no, event))
    return seen_positions


def snapshot(connection):
    accounts = {
        row[0]: {"balance_cents": row[1], "version": row[2]}
        for row in connection.execute(
            "SELECT account_id,balance_cents,version FROM accounts ORDER BY account_id"
        )
    }
    applied = [row[0] for row in connection.execute(
        "SELECT event_id FROM applied_events ORDER BY event_id"
    )]
    cursor = connection.execute(
        "SELECT segment,line_no,event_id FROM consumer_cursor WHERE consumer=?",
        (CONSUMER,),
    ).fetchone()
    return {
        "accounts": accounts,
        "applied_event_ids": applied,
        "cursor": None if cursor is None else {
            "segment": cursor[0], "line_no": cursor[1], "event_id": cursor[2]
        },
    }


def stale_cursor(connection, all_records):
    applied = {row[0] for row in connection.execute("SELECT event_id FROM applied_events")}
    cursor = connection.execute(
        "SELECT segment,line_no,event_id FROM consumer_cursor WHERE consumer=?",
        (CONSUMER,),
    ).fetchone()
    if cursor is None:
        return bool(applied)
    before_or_at = []
    for segment, line_no, event in all_records:
        before_or_at.append(event["event_id"])
        if (segment, line_no) == (cursor[0], cursor[1]):
            break
    return any(event_id not in set(before_or_at) for event_id in applied)


def recover(database: Path, acknowledge: bool):
    all_records = records()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA foreign_keys=ON")
    before = snapshot(connection)
    is_stale = stale_cursor(connection, all_records)
    if is_stale and not acknowledge:
        raise SystemExit(
            "refusing recovery: applied_events is ahead of consumer_cursor; "
            "inspect evidence and pass --acknowledge-stale-cursor"
        )
    newly_applied = []
    duplicate_deliveries = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        for segment, line_no, event in all_records:
            inserted = connection.execute(
                "INSERT OR IGNORE INTO applied_events "
                "(event_id,account_id,delta_cents,source_segment,source_line,applied_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    event["event_id"], event["account_id"], event["delta_cents"],
                    segment, line_no, event["occurred_at"],
                ),
            ).rowcount
            if inserted:
                connection.execute(
                    "INSERT INTO accounts(account_id,balance_cents,version) VALUES(?,?,1) "
                    "ON CONFLICT(account_id) DO UPDATE SET "
                    "balance_cents=balance_cents+excluded.balance_cents, "
                    "version=version+1",
                    (event["account_id"], event["delta_cents"]),
                )
                newly_applied.append(event["event_id"])
            else:
                duplicate_deliveries.append({
                    "event_id": event["event_id"],
                    "segment": segment,
                    "line_no": line_no,
                })
        final_segment, final_line, final_event = all_records[-1]
        connection.execute(
            "INSERT INTO consumer_cursor(consumer,segment,line_no,event_id) VALUES(?,?,?,?) "
            "ON CONFLICT(consumer) DO UPDATE SET "
            "segment=excluded.segment,line_no=excluded.line_no,event_id=excluded.event_id",
            (CONSUMER, final_segment, final_line, final_event["event_id"]),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    after = snapshot(connection)
    connection.close()
    return {
        "schema_version": 1,
        "consumer": CONSUMER,
        "stale_cursor_acknowledged": is_stale and acknowledge,
        "newly_applied_event_ids": newly_applied,
        "duplicate_deliveries": duplicate_deliveries,
        "before": before,
        "after": after,
        "journal_end": {
            "segment": final_segment,
            "line_no": final_line,
            "event_id": final_event["event_id"],
        },
        "completed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect or recover the local journal projection")
    parser.add_argument("command", choices=("inspect", "recover", "verify"))
    parser.add_argument("--database", default="state/projection.db")
    parser.add_argument("--acknowledge-stale-cursor", action="store_true")
    parser.add_argument("--receipt", default="out/recovery_receipt.json")
    args = parser.parse_args()
    database = (ROOT / args.database).resolve()
    if ROOT not in database.parents:
        raise SystemExit("database must stay inside the repository")
    if args.command == "inspect":
        connection = sqlite3.connect(database)
        result = snapshot(connection)
        result["stale_cursor"] = stale_cursor(connection, records())
        connection.close()
    elif args.command == "verify":
        connection = sqlite3.connect(database)
        result = snapshot(connection)
        result["integrity_check"] = connection.execute("PRAGMA integrity_check").fetchone()[0]
        result["stale_cursor"] = stale_cursor(connection, records())
        connection.close()
    else:
        result = recover(database, args.acknowledge_stale_cursor)
        receipt = (ROOT / args.receipt).resolve()
        if ROOT not in receipt.parents:
            raise SystemExit("receipt must stay inside the repository")
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
