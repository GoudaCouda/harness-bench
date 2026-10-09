#!/usr/bin/env python3
"""Deterministic final-state verifier for case_20."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path
from typing import Any


MAX_WORKSPACE_ENTRIES = 96
MAX_WORKSPACE_DEPTH = 8
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 8 * 1024 * 1024
MAX_REGISTER_BYTES = 256 * 1024
MAX_DATABASE_BYTES = 8 * 1024 * 1024
MAX_DOWNLOAD_ROWS = 64
MAX_REMINDER_ROWS = 32


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_sha256_file(path: Path, maximum: int) -> tuple[str | None, str | None]:
    try:
        mode = path.lstat().st_mode
        size = path.lstat().st_size
        if not stat.S_ISREG(mode):
            return None, "not_regular"
        if size > maximum:
            return None, "oversized"
        digest = hashlib.sha256()
        observed = 0
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(min(1024 * 1024, maximum + 1 - observed))
                if not chunk:
                    break
                observed += len(chunk)
                if observed > maximum:
                    return None, "oversized_during_read"
                digest.update(chunk)
        if observed != size:
            return None, "size_changed_during_read"
        return digest.hexdigest(), None
    except OSError as exc:
        return None, f"unreadable:{type(exc).__name__}"


def canonical_json_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def add(checks: list[dict[str, Any]], check_id: str, passed: bool, **evidence: Any) -> None:
    checks.append({"check_id": check_id, "passed": bool(passed), "evidence": evidence})


def safe_inventory(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        return records, [f"workspace_root_unreadable:{type(exc).__name__}"]
    if not stat.S_ISDIR(root_mode) or stat.S_ISLNK(root_mode):
        return records, ["workspace_root_invalid"]
    pending: list[tuple[Path, int]] = [(root, 0)]
    total_size = 0
    entry_count = 0
    while pending:
        directory, depth = pending.pop()
        try:
            entries: list[os.DirEntry[str]] = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries.append(entry)
                    if entry_count + len(entries) > MAX_WORKSPACE_ENTRIES:
                        errors.append("workspace_entry_limit_exceeded")
                        return records, errors
            entries.sort(key=lambda entry: entry.name)
        except OSError as exc:
            relative = directory.relative_to(root).as_posix() or "."
            errors.append(f"unreadable_directory:{relative}:{type(exc).__name__}")
            continue
        for entry in entries:
            entry_count += 1
            relative = Path(entry.path).relative_to(root).as_posix()
            if entry_count > MAX_WORKSPACE_ENTRIES:
                errors.append("workspace_entry_limit_exceeded")
                return records, errors
            if depth + 1 > MAX_WORKSPACE_DEPTH:
                errors.append(f"workspace_depth_limit_exceeded:{relative}")
                continue
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
                size = entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                errors.append(f"unreadable_metadata:{relative}:{type(exc).__name__}")
                continue
            path = Path(entry.path)
            if stat.S_ISLNK(mode):
                errors.append(f"symlink:{relative}")
            elif stat.S_ISDIR(mode):
                records.append({"path": relative, "type": "directory"})
                pending.append((path, depth + 1))
            elif stat.S_ISREG(mode):
                total_size += size
                if total_size > MAX_TOTAL_FILE_BYTES:
                    errors.append("workspace_total_size_limit_exceeded")
                    return records, errors
                digest, digest_error = bounded_sha256_file(path, MAX_FILE_BYTES)
                record = {"path": relative, "type": "file", "size_bytes": size, "sha256": digest}
                records.append(record)
                if digest_error:
                    errors.append(f"file_{digest_error}:{relative}")
            else:
                errors.append(f"special:{relative}")
    return records, errors


def expected_workspace_entries(case_root: Path, reference: dict[str, Any]) -> set[tuple[str, str]]:
    expected = {("inputs", "directory"), ("archive", "directory"), ("outputs", "directory")}
    for path in sorted((case_root / "fixtures/workspace_seed/inputs").iterdir()):
        expected.add((f"inputs/{path.name}", "file"))
    for item in reference["archive_files"]:
        pure = Path(item["path"])
        for index in range(1, len(pure.parts)):
            expected.add((Path(*pure.parts[:index]).as_posix(), "directory"))
        expected.add((item["path"], "file"))
    expected.add(("outputs/material_register.csv", "file"))
    return expected


def source_projection(database: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        people = [
            {"person_id": row["person_id"], "name": row["name"], "is_roster_member": bool(row["is_roster_member"])}
            for row in connection.execute("SELECT person_id, name, is_roster_member FROM people ORDER BY rowid")
        ]
        messages = [dict(row) for row in connection.execute("SELECT message_id, sender_id, channel, sent_at, text FROM messages ORDER BY rowid")]
        attachments = [
            dict(row)
            for row in connection.execute(
                """SELECT attachment_id, message_id, owner_id, material_type, original_filename,
                          replaces_attachment_id, sha256, size_bytes FROM attachments ORDER BY rowid"""
            )
        ]
        blob_checks = [
            {
                "attachment_id": row["attachment_id"],
                "stored_sha256": row["sha256"],
                "computed_sha256": hashlib.sha256(row["content"]).hexdigest(),
                "stored_size": row["size_bytes"],
                "computed_size": len(row["content"]),
            }
            for row in connection.execute("SELECT attachment_id, content, sha256, size_bytes FROM attachments ORDER BY rowid")
        ]
        projection = {
            "schema_version": "case20_collaboration_seed_v1",
            "fixed_time": metadata["fixed_time"],
            "channel": metadata["channel"],
            "people": people,
            "messages": messages,
            "attachments": attachments,
        }
        return projection, blob_checks, metadata
    finally:
        connection.close()


def verify(case_root: Path, work_root: Path) -> dict[str, Any]:
    reference = json.loads((case_root / "oracle/reference_state.json").read_text(encoding="utf-8"))
    case = json.loads((case_root / "case.json").read_text(encoding="utf-8"))
    seed = json.loads((case_root / "fixtures/service_seed.json").read_text(encoding="utf-8"))
    workspace = work_root / "workspace"
    database = work_root / "service_state/collaboration.sqlite"
    checks: list[dict[str, Any]] = []

    inventory, inventory_errors = safe_inventory(workspace)
    actual_entries = {(item["path"], item["type"]) for item in inventory}
    expected_entries = expected_workspace_entries(case_root, reference)
    add(
        checks,
        "workspace_exact_structure",
        not inventory_errors and actual_entries == expected_entries,
        missing_count=len(expected_entries - actual_entries),
        extra_count=len(actual_entries - expected_entries),
        unsafe_entry_count=len(inventory_errors),
    )

    input_expected = {
        path.name: {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
            "mode": 0o444,
        }
        for path in (case_root / "fixtures/workspace_seed/inputs").iterdir()
        if path.is_file() and not path.is_symlink()
    }
    input_actual = {}
    for name in input_expected:
        path = workspace / "inputs" / name
        if path.is_file() and not path.is_symlink():
            digest, error = bounded_sha256_file(path, MAX_FILE_BYTES)
            if error is None:
                input_actual[name] = {
                    "sha256": digest,
                    "size_bytes": path.stat().st_size,
                    "mode": stat.S_IMODE(path.stat().st_mode),
                }
    add(
        checks,
        "input_assets_unchanged",
        input_actual == input_expected,
        expected_count=len(input_expected),
        matching_count=sum(input_actual.get(name) == expected for name, expected in input_expected.items()),
    )

    database_guard_ok = False
    try:
        database_mode = database.lstat().st_mode
        database_guard_ok = (
            stat.S_ISREG(database_mode)
            and not database.is_symlink()
            and database.lstat().st_size <= MAX_DATABASE_BYTES
        )
    except OSError:
        database_guard_ok = False
    add(checks, "service_database_bounds", database_guard_ok, maximum_bytes=MAX_DATABASE_BYTES)

    try:
        if not database_guard_ok:
            raise ValueError("database bounds failed")
        projection, blob_checks, metadata = source_projection(database)
        seed_attachments = []
        for item in seed["attachments"]:
            payload = (case_root / "fixtures" / item["fixture_path"]).read_bytes()
            seed_attachments.append(
                {
                    **{key: value for key, value in item.items() if key != "fixture_path"},
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
            )
        expected_projection = {
            "schema_version": seed["schema_version"],
            "fixed_time": seed["fixed_time"],
            "channel": seed["channel"],
            "people": seed["people"],
            "messages": seed["messages"],
            "attachments": seed_attachments,
        }
        source_ok = projection == expected_projection and metadata.get("source_projection_sha256") == canonical_json_sha(expected_projection)
        blobs_ok = all(
            item["stored_sha256"] == item["computed_sha256"] and item["stored_size"] == item["computed_size"]
            for item in blob_checks
        )
    except (OSError, ValueError, KeyError, sqlite3.Error):
        source_ok = False
        blobs_ok = False
        blob_checks = []
    add(checks, "source_service_immutable", source_ok, source_record_count=len(seed["messages"]) + len(seed["attachments"]))
    add(checks, "source_attachment_blobs_immutable", blobs_ok, checked_count=len(blob_checks))

    archive_actual = {
        item["path"]: item.get("sha256")
        for item in inventory
        if item["type"] == "file" and item["path"].startswith("archive/")
    }
    archive_expected = {item["path"]: item["sha256"] for item in reference["archive_files"]}
    add(
        checks,
        "archive_exact_set",
        set(archive_actual) == set(archive_expected),
        expected_count=len(archive_expected),
        actual_count=len(archive_actual),
    )
    add(
        checks,
        "archive_byte_fidelity",
        archive_actual == archive_expected,
        matching_count=sum(archive_actual.get(path) == digest for path, digest in archive_expected.items()),
    )
    pdf_ok = True
    pdf_count = 0
    for relative in archive_expected:
        path = workspace / relative
        if not path.is_file() or path.is_symlink():
            pdf_ok = False
            continue
        digest, error = bounded_sha256_file(path, MAX_FILE_BYTES)
        if error or digest != archive_expected[relative]:
            pdf_ok = False
            continue
        try:
            data = path.read_bytes()
        except OSError:
            pdf_ok = False
            continue
        pdf_count += 1
        pdf_ok = pdf_ok and data.startswith(b"%PDF-1.4\n") and b"\nxref\n" in data and data.rstrip().endswith(b"%%EOF")
    add(checks, "archive_pdf_structure", pdf_ok and pdf_count == len(archive_expected), checked_count=pdf_count)

    register_path = workspace / "outputs/material_register.csv"
    header: list[str] = []
    rows: list[dict[str, str]] = []
    register_parse_ok = False
    try:
        register_stat = register_path.lstat()
        if not stat.S_ISREG(register_stat.st_mode) or register_path.is_symlink():
            raise ValueError("register is not a regular file")
        if register_stat.st_size > MAX_REGISTER_BYTES:
            raise ValueError("register is oversized")
        with register_path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            header = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        register_parse_ok = True
    except (OSError, UnicodeError, csv.Error, ValueError):
        pass
    add(checks, "register_schema", register_parse_ok and header == reference["register_fields"], column_count=len(header))
    add(checks, "register_exact_rows", register_parse_ok and rows == reference["register_rows"], expected_rows=6, actual_rows=len(rows))

    downloads: list[dict[str, Any]] = []
    reminders: list[dict[str, Any]] = []
    download_count = 0
    reminder_count = 0
    db_schema_ok = False
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            db_schema_ok = tables == {"metadata", "people", "messages", "attachments", "download_events", "reminder_events"}
            download_count = connection.execute("SELECT count(*) FROM download_events").fetchone()[0]
            reminder_count = connection.execute("SELECT count(*) FROM reminder_events").fetchone()[0]
            if download_count <= MAX_DOWNLOAD_ROWS:
                downloads = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT attachment_id, destination, occurred_at FROM download_events LIMIT ?",
                        (MAX_DOWNLOAD_ROWS + 1,),
                    )
                ]
            if reminder_count <= MAX_REMINDER_ROWS:
                reminders = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT recipient_id, body, sent_at FROM reminder_events LIMIT ?",
                        (MAX_REMINDER_ROWS + 1,),
                    )
                ]
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        pass
    add(checks, "service_schema_no_extra_state", db_schema_ok, table_count=6 if db_schema_ok else 0)
    expected_downloads = sorted(
        [
            {"attachment_id": item["attachment_id"], "destination": item["path"], "occurred_at": reference["fixed_time"]}
            for item in reference["archive_files"]
        ],
        key=lambda item: (item["attachment_id"], item["destination"]),
    )
    add(
        checks,
        "download_audit_exact",
        sorted(downloads, key=lambda item: (item["attachment_id"], item["destination"])) == expected_downloads,
        expected_count=len(expected_downloads),
        actual_count=download_count,
    )
    expected_reminders = sorted(
        [
            {"recipient_id": item["recipient_id"], "body": item["body"], "sent_at": reference["fixed_time"]}
            for item in reference["reminders"]
        ],
        key=lambda item: item["recipient_id"],
    )
    sorted_reminders = sorted(reminders, key=lambda item: item["recipient_id"])
    recipient_ok = [item["recipient_id"] for item in sorted_reminders] == [item["recipient_id"] for item in expected_reminders]
    add(
        checks,
        "reminder_recipients_exact",
        recipient_ok,
        expected_count=3,
        actual_count=reminder_count,
    )
    add(checks, "reminder_content_exact", sorted_reminders == expected_reminders, matching_count=sum(item in expected_reminders for item in reminders))

    passed_count = sum(item["passed"] for item in checks)
    failed = [item["check_id"] for item in checks if not item["passed"]]
    return {
        "schema_version": "case20_verifier_result_v1",
        "task_id": "case_20",
        "case_version": case["case_version"],
        "status": "passed" if not failed else "failed",
        "score": 1.0 if not failed else 0.0,
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed_count": passed_count,
            "failed_count": len(failed),
            "failed_check_ids": failed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.case_root.resolve(strict=True), args.work_root.resolve(strict=True))
        exit_code = 0 if result["status"] == "passed" else 1
    except Exception as exc:
        result = {
            "schema_version": "case20_verifier_result_v1",
            "task_id": "case_20",
            "case_version": "1.2.0",
            "status": "invalid",
            "score": 0.0,
            "checks": [],
            "summary": {"check_count": 0, "passed_count": 0, "failed_count": 0, "failed_check_ids": [type(exc).__name__]},
        }
        exit_code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
