#!/usr/bin/env python3
"""Hidden deterministic verifier for the synthetic hotel booking state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import sqlite3
import stat
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = CASE_ROOT / "fixtures" / "initial_database.json"
RESET_PATH = CASE_ROOT / "environment" / "reset.py"
AGENT_FILE_SOURCES = {
    "task.md": CASE_ROOT / "fixtures" / "agent_task.md",
    "tool_client.py": CASE_ROOT / "fixtures" / "tool_client.py",
    "tool_contract.json": CASE_ROOT / "fixtures" / "tool_contract.json",
}
EXPECTED_TABLES = {
    "audit_events",
    "booking_nights",
    "bookings",
    "hotels",
    "inventory",
    "meta",
    "users",
}
EXPECTED_COLUMNS = {
    "audit_events": ["event_id", "event_type", "object_id", "payload_json", "created_at"],
    "booking_nights": ["booking_id", "stay_date"],
    "bookings": ["booking_id", "request_id", "user_id", "hotel_id", "check_in", "check_out", "adults", "children", "room_type", "status", "total_cny", "created_at"],
    "hotels": ["hotel_id", "name", "city", "district", "breakfast_included", "non_smoking_family_room", "nightly_rate_cny"],
    "inventory": ["hotel_id", "stay_date", "room_type", "total_rooms", "available_rooms"],
    "meta": ["key", "value"],
    "users": ["user_id", "display_name", "status"],
}
EXPECTED_BOOKING = {
    "booking_id": "BKG-NW16-001",
    "request_id": "REQ-NW16-001",
    "user_id": "CUS-042",
    "hotel_id": "H-CJ-002",
    "check_in": "2026-11-18",
    "check_out": "2026-11-21",
    "adults": 2,
    "children": 1,
    "room_type": "family_standard",
    "status": "confirmed",
    "total_cny": 1794,
    "created_at": "2026-07-20T09:00:00+08:00",
}
EXPECTED_NIGHTS = ["2026-11-18", "2026-11-19", "2026-11-20"]
EXPECTED_MODES = {
    ".": 0o750,
    "agent_workspace": 0o750,
    "agent_workspace/task.md": 0o440,
    "agent_workspace/tool_client.py": 0o440,
    "agent_workspace/tool_contract.json": 0o440,
    "state": 0o750,
    "state/hotel_booking.db": 0o660,
}
MAX_ENTRY_COUNT = 64
MAX_DEPTH = 3
MAX_TOTAL_REGULAR_BYTES = 9 * 1024 * 1024
MAX_FILE_BYTES = {
    "agent_workspace/task.md": 64 * 1024,
    "agent_workspace/tool_client.py": 64 * 1024,
    "agent_workspace/tool_contract.json": 64 * 1024,
    "state/hotel_booking.db": 8 * 1024 * 1024,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_sha256_file(path: Path) -> str | None:
    try:
        return sha256_file(path)
    except OSError:
        return None


def add_check(checks: list[dict[str, Any]], check_id: str, passed: bool, **evidence: Any) -> None:
    checks.append({"check_id": check_id, "passed": bool(passed), "evidence": evidence})


def entry_kind(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "other"


def scan_tree(work_root: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    complete = True
    errors: list[str] = []
    try:
        root_stat = os.lstat(work_root)
    except OSError as exc:
        return {"items": items, "complete": False, "errors": [type(exc).__name__], "root": None}
    root = {
        "path": ".",
        "kind": entry_kind(root_stat.st_mode),
        "mode": stat.S_IMODE(root_stat.st_mode),
        "uid": root_stat.st_uid,
        "gid": root_stat.st_gid,
        "nlink": root_stat.st_nlink,
        "size": root_stat.st_size,
    }
    if root["kind"] != "directory":
        return {"items": items, "complete": False, "errors": ["unsafe_root"], "root": root}
    stack: list[tuple[Path, int]] = [(work_root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda value: value.name)
        except OSError as exc:
            complete = False
            errors.append(type(exc).__name__)
            continue
        for entry in entries:
            if len(items) >= MAX_ENTRY_COUNT:
                complete = False
                errors.append("entry_limit")
                stack.clear()
                break
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                complete = False
                errors.append(type(exc).__name__)
                continue
            path = Path(entry.path)
            relative = path.relative_to(work_root).as_posix()
            kind = entry_kind(metadata.st_mode)
            item = {
                "path": relative,
                "kind": kind,
                "mode": stat.S_IMODE(metadata.st_mode),
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
                "nlink": metadata.st_nlink,
                "size": metadata.st_size,
            }
            if kind == "file" and relative in MAX_FILE_BYTES and metadata.st_size <= MAX_FILE_BYTES[relative]:
                try:
                    item["sha256"] = sha256_file(path)
                except OSError as exc:
                    item["sha256"] = f"unreadable:{type(exc).__name__}"
                    complete = False
                    errors.append(type(exc).__name__)
            items.append(item)
            if kind == "directory":
                if depth + 1 > MAX_DEPTH:
                    complete = False
                    errors.append("depth_limit")
                else:
                    stack.append((path, depth + 1))
    return {"items": items, "complete": complete, "errors": sorted(set(errors)), "root": root}


def children(scan: dict[str, Any], parent: str) -> list[str]:
    prefix = "" if parent == "." else f"{parent}/"
    result = []
    for item in scan["items"]:
        relative = item["path"]
        if relative.startswith(prefix) and "/" not in relative[len(prefix):]:
            result.append(relative[len(prefix):])
    return sorted(result)


def inspect_filesystem(work_root: Path, checks: list[dict[str, Any]], trusted: dict[str, Any]) -> tuple[Path | None, str]:
    scan = scan_tree(work_root)
    fingerprint = hashlib.sha256(canonical_bytes({"root": scan["root"], "items": scan["items"]})).hexdigest()
    items = {item["path"]: item for item in scan["items"]}
    root = scan["root"]
    symbolic = [item["path"] for item in scan["items"] if item["kind"] == "symlink"]
    special = [item["path"] for item in scan["items"] if item["kind"] not in {"directory", "file", "symlink"}]
    hardlinks = [item["path"] for item in scan["items"] if item["kind"] == "file" and item["nlink"] != 1]
    total_regular = sum(item["size"] for item in scan["items"] if item["kind"] == "file")
    per_file_ok = all(item["size"] <= MAX_FILE_BYTES.get(item["path"], 0) for item in scan["items"] if item["kind"] == "file")
    add_check(checks, "filesystem_scan_complete", scan["complete"], error_type_count=len(scan["errors"]), entry_count=len(scan["items"]))
    add_check(checks, "no_symbolic_links", not symbolic, symbolic_link_count=len(symbolic))
    add_check(checks, "no_special_files", not special, special_file_count=len(special))
    add_check(checks, "no_hard_links", not hardlinks, hard_link_count=len(hardlinks))
    add_check(checks, "resource_bounds", scan["complete"] and len(scan["items"]) <= MAX_ENTRY_COUNT and total_regular <= MAX_TOTAL_REGULAR_BYTES and per_file_ok, entry_count=len(scan["items"]), total_regular_bytes=total_regular)
    add_check(checks, "exact_root_entries", scan["complete"] and children(scan, ".") == ["agent_workspace", "state"], entry_count=len(children(scan, ".")))
    add_check(checks, "exact_agent_workspace", scan["complete"] and children(scan, "agent_workspace") == ["task.md", "tool_client.py", "tool_contract.json"], entry_count=len(children(scan, "agent_workspace")))
    add_check(checks, "exact_state_files", scan["complete"] and children(scan, "state") == ["hotel_booking.db"], entry_count=len(children(scan, "state")))
    modes_ok = root is not None and root["mode"] == EXPECTED_MODES["."]
    ownership_ok = root is not None
    for relative, expected_mode in EXPECTED_MODES.items():
        if relative == ".":
            continue
        item = items.get(relative)
        modes_ok = modes_ok and item is not None and item["mode"] == expected_mode
        ownership_ok = ownership_ok and item is not None and item["uid"] == root["uid"] and item["gid"] == root["gid"]
    add_check(checks, "exact_permissions", modes_ok, expected_entry_count=len(EXPECTED_MODES))
    add_check(checks, "ownership_consistent", ownership_ok, expected_entry_count=len(EXPECTED_MODES))
    agent_hashes_ok = True
    for name, expected_hash in trusted["agent_hashes"].items():
        item = items.get(f"agent_workspace/{name}")
        agent_hashes_ok = agent_hashes_ok and item is not None and item.get("sha256") == expected_hash
    add_check(checks, "agent_inputs_unchanged", agent_hashes_ok, checked_file_count=len(trusted["agent_hashes"]))
    database_item = items.get("state/hotel_booking.db")
    readable = (
        database_item is not None
        and database_item["kind"] == "file"
        and database_item["nlink"] == 1
        and database_item["size"] <= MAX_FILE_BYTES["state/hotel_booking.db"]
        and isinstance(database_item.get("sha256"), str)
        and not database_item["sha256"].startswith("unreadable:")
    )
    if not readable:
        add_check(checks, "candidate_state_readable", False, database_regular=False)
        return None, fingerprint
    return work_root / "state" / "hotel_booking.db", fingerprint


def schema_objects(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    return [{"type": row[0], "name": row[1], "table": row[2], "sql": row[3]} for row in rows]


def load_trusted_contract() -> dict[str, Any]:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    namespace = runpy.run_path(str(RESET_PATH), run_name="case16_reset_contract")
    schema_sql = namespace.get("SCHEMA_SQL")
    if not isinstance(schema_sql, str):
        raise ValueError("trusted schema is missing")
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(schema_sql)
        expected_schema = schema_objects(connection)
    finally:
        connection.close()
    target = expected_state(seed)
    return {
        "seed": seed,
        "target": target,
        "schema_sha256": hashlib.sha256(canonical_bytes(expected_schema)).hexdigest(),
        "agent_hashes": {name: sha256_file(path) for name, path in AGENT_FILE_SOURCES.items()},
    }


def table_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    columns = EXPECTED_COLUMNS[table]
    selected = ", ".join(f'"{column}"' for column in columns)
    order = ", ".join(f'"{column}"' for column in columns)
    rows = connection.execute(f'SELECT {selected} FROM "{table}" ORDER BY {order} LIMIT 1001').fetchall()
    return [dict(zip(columns, row, strict=True)) for row in rows]


def expected_state(seed: dict[str, Any]) -> dict[str, Any]:
    audit_payload = json.dumps(
        {"check_in": "2026-11-18", "check_out": "2026-11-21", "hotel_id": "H-CJ-002", "request_id": "REQ-NW16-001", "user_id": "CUS-042"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    inventory = []
    for hotel in seed["hotels"]:
        for stay_date in seed["inventory_dates"]:
            available = seed["initial_rooms_per_hotel_date"]
            if hotel["hotel_id"] == "H-CJ-002" and stay_date in EXPECTED_NIGHTS:
                available -= 1
            inventory.append({
                "hotel_id": hotel["hotel_id"],
                "stay_date": stay_date,
                "room_type": seed["room_type"],
                "total_rooms": seed["initial_rooms_per_hotel_date"],
                "available_rooms": available,
            })
    return {
        "audit_events": [{"event_id": 1, "event_type": "booking_created", "object_id": "BKG-NW16-001", "payload_json": audit_payload, "created_at": "2026-07-20T09:00:00+08:00"}],
        "booking_nights": [{"booking_id": "BKG-NW16-001", "stay_date": stay_date} for stay_date in EXPECTED_NIGHTS],
        "bookings": [EXPECTED_BOOKING],
        "hotels": seed["hotels"],
        "inventory": inventory,
        "meta": seed["meta"],
        "users": seed["users"],
    }


def finalize(checks: list[dict[str, Any]], final_hash: str, database_hash: str | None = None) -> dict[str, Any]:
    passed_count = sum(check["passed"] for check in checks)
    verdict = "accept" if passed_count == len(checks) else "reject"
    evidence: dict[str, Any] = {
        "check_count": len(checks),
        "passed_count": passed_count,
        "verifier_version": "1.1.0",
    }
    if database_hash is not None:
        evidence["database_sha256"] = database_hash
    return {
        "schema_version": "nami_work_case16_verifier_result_v1",
        "verdict": verdict,
        "score": passed_count / len(checks),
        "final_state_sha256": final_hash,
        "checks": checks,
        "evidence": evidence,
    }


def verify(work_root: Path, trusted: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    database, filesystem_hash = inspect_filesystem(work_root, checks, trusted)
    if database is None:
        return finalize(checks, filesystem_hash)
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro&immutable=1", uri=True)
        try:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            connection.set_progress_handler(lambda: 1, 2_000_000)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            add_check(checks, "candidate_state_readable", True, database_regular=True)
            add_check(checks, "database_integrity", integrity == "ok" and not foreign_key_violations and user_version == 1, foreign_key_violation_count=len(foreign_key_violations), user_version=user_version)
            actual_schema = schema_objects(connection)
            actual_schema_hash = hashlib.sha256(canonical_bytes(actual_schema)).hexdigest()
            add_check(checks, "exact_database_schema", actual_schema_hash == trusted["schema_sha256"], object_count=len(actual_schema))
            tables = {item["name"] for item in actual_schema if item["type"] == "table"}
            non_tables = [item for item in actual_schema if item["type"] != "table"]
            add_check(checks, "exact_database_objects", tables == EXPECTED_TABLES and not non_tables, table_count=len(tables), non_table_object_count=len(non_tables))
            columns_ok = all(
                [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()] == columns
                for table, columns in EXPECTED_COLUMNS.items()
            )
            add_check(checks, "exact_database_columns", columns_ok, checked_table_count=len(EXPECTED_COLUMNS))
            state = {table: table_rows(connection, table) for table in sorted(EXPECTED_TABLES)}
        finally:
            connection.close()
    except (OSError, ValueError, KeyError, IndexError, sqlite3.Error) as exc:
        if not any(check["check_id"] == "candidate_state_readable" for check in checks):
            add_check(checks, "candidate_state_readable", False, error_type=type(exc).__name__)
        else:
            add_check(checks, "candidate_state_queryable", False, error_type=type(exc).__name__)
        return finalize(checks, filesystem_hash, safe_sha256_file(database))

    seed = trusted["seed"]
    target = trusted["target"]
    eligible_hotels = sorted(
        hotel["hotel_id"]
        for hotel in seed["hotels"]
        if hotel["city"] == "澄江市"
        and hotel["district"] == "中心区"
        and hotel["breakfast_included"] == 1
        and hotel["non_smoking_family_room"] == 1
        and hotel["nightly_rate_cny"] <= 620
    )
    add_check(checks, "unique_eligible_hotel", eligible_hotels == ["H-CJ-002"], eligible_count=len(eligible_hotels))
    booking = state["bookings"][0] if len(state["bookings"]) == 1 else None
    add_check(checks, "unique_booking", len(state["bookings"]) == 1, booking_count=len(state["bookings"]))
    add_check(checks, "correct_hotel", booking is not None and booking["hotel_id"] == "H-CJ-002", matched=booking is not None and booking["hotel_id"] == "H-CJ-002")
    add_check(checks, "correct_dates", booking is not None and booking["check_in"] == "2026-11-18" and booking["check_out"] == "2026-11-21" and state["booking_nights"] == target["booking_nights"], night_count=len(state["booking_nights"]))
    add_check(checks, "correct_party", booking is not None and booking["adults"] == 2 and booking["children"] == 1 and booking["room_type"] == "family_standard", matched=booking is not None and booking["adults"] == 2 and booking["children"] == 1)
    add_check(checks, "correct_booking_fields", state["bookings"] == target["bookings"], booking_count=len(state["bookings"]))
    add_check(checks, "exact_inventory_change", state["inventory"] == target["inventory"], inventory_row_count=len(state["inventory"]))
    add_check(checks, "protected_users_unchanged", state["users"] == target["users"], user_count=len(state["users"]))
    add_check(checks, "protected_hotel_catalog_unchanged", state["hotels"] == target["hotels"], hotel_count=len(state["hotels"]))
    add_check(checks, "exact_audit_event", state["audit_events"] == target["audit_events"], audit_event_count=len(state["audit_events"]))
    add_check(checks, "exact_terminal_state", state == target, logical_table_count=len(state))
    final_hash = hashlib.sha256(canonical_bytes(state)).hexdigest()
    return finalize(checks, final_hash, sha256_file(database))


def invalid_result(error_type: str) -> dict[str, Any]:
    return {
        "schema_version": "nami_work_case16_verifier_result_v1",
        "verdict": "invalid",
        "score": 0,
        "final_state_sha256": "0" * 64,
        "checks": [{"check_id": "trusted_verifier_runtime_valid", "passed": False, "evidence": {"error_type": error_type}}],
        "evidence": {"check_count": 1, "passed_count": 0, "verifier_version": "1.1.0"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        trusted = load_trusted_contract()
        result = verify(args.work_root, trusted)
    except (OSError, ValueError, KeyError, IndexError, sqlite3.Error, json.JSONDecodeError) as exc:
        result = invalid_result(type(exc).__name__)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        try:
            if args.output.exists() or args.output.is_symlink():
                raise FileExistsError("output exists")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"status": "invalid", "error": type(exc).__name__}, sort_keys=True))
            return 2
        print(json.dumps({"verdict": result["verdict"]}, sort_keys=True))
    else:
        print(rendered, end="")
    if result["verdict"] == "accept":
        return 0
    if result["verdict"] == "reject":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
