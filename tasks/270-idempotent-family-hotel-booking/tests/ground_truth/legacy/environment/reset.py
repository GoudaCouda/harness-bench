#!/usr/bin/env python3
"""Create the deterministic case_16 runtime from the immutable JSON seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = CASE_ROOT / "fixtures" / "initial_database.json"
AGENT_FILES = {
    "task.md": CASE_ROOT / "fixtures" / "agent_task.md",
    "tool_client.py": CASE_ROOT / "fixtures" / "tool_client.py",
    "tool_contract.json": CASE_ROOT / "fixtures" / "tool_contract.json",
}
TABLE_ORDER = (
    "audit_events",
    "booking_nights",
    "bookings",
    "hotels",
    "inventory",
    "meta",
    "users",
)


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
PRAGMA user_version = 1;

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE hotels (
    hotel_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    district TEXT NOT NULL,
    breakfast_included INTEGER NOT NULL CHECK (breakfast_included IN (0, 1)),
    non_smoking_family_room INTEGER NOT NULL CHECK (non_smoking_family_room IN (0, 1)),
    nightly_rate_cny INTEGER NOT NULL CHECK (nightly_rate_cny > 0)
) WITHOUT ROWID;

CREATE TABLE inventory (
    hotel_id TEXT NOT NULL REFERENCES hotels(hotel_id),
    stay_date TEXT NOT NULL,
    room_type TEXT NOT NULL CHECK (room_type = 'family_standard'),
    total_rooms INTEGER NOT NULL CHECK (total_rooms >= 0),
    available_rooms INTEGER NOT NULL CHECK (available_rooms >= 0 AND available_rooms <= total_rooms),
    PRIMARY KEY (hotel_id, stay_date, room_type)
) WITHOUT ROWID;

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'disabled'))
) WITHOUT ROWID;

CREATE TABLE bookings (
    booking_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    hotel_id TEXT NOT NULL REFERENCES hotels(hotel_id),
    check_in TEXT NOT NULL,
    check_out TEXT NOT NULL,
    adults INTEGER NOT NULL CHECK (adults > 0),
    children INTEGER NOT NULL CHECK (children >= 0),
    room_type TEXT NOT NULL CHECK (room_type = 'family_standard'),
    status TEXT NOT NULL CHECK (status = 'confirmed'),
    total_cny INTEGER NOT NULL CHECK (total_cny > 0),
    created_at TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE booking_nights (
    booking_id TEXT NOT NULL REFERENCES bookings(booking_id),
    stay_date TEXT NOT NULL,
    PRIMARY KEY (booking_id, stay_date)
) WITHOUT ROWID;

CREATE TABLE audit_events (
    event_id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_database_state(database_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        state: dict[str, Any] = {}
        for table in TABLE_ORDER:
            columns = [
                row[1]
                for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            ]
            order = ", ".join(f'"{column}"' for column in columns)
            rows = connection.execute(
                f'SELECT * FROM "{table}" ORDER BY {order}'
            ).fetchall()
            state[table] = [dict(zip(columns, row, strict=True)) for row in rows]
        return state
    finally:
        connection.close()


def require_fresh_directory(work_root: Path, allowed_parent: Path) -> Path:
    if allowed_parent.is_symlink() or not allowed_parent.is_dir():
        raise ValueError("allowed parent must be an existing real directory")
    resolved_parent = allowed_parent.resolve(strict=True)
    if work_root.is_symlink():
        raise ValueError("work root must not be a symbolic link")
    resolved = work_root.resolve(strict=False)
    if resolved == Path(resolved.anchor):
        raise ValueError("refusing filesystem root")
    if resolved.parent != resolved_parent:
        raise ValueError("work root must be a direct child of the allowed parent")
    if work_root.exists():
        if not work_root.is_dir():
            raise ValueError("work root exists and is not a directory")
        if any(work_root.iterdir()):
            raise ValueError("work root must be empty")
    else:
        work_root.mkdir(parents=True, mode=0o750)
    # CephFS parents are commonly setgid; normalize the runtime contract after
    # creation so local and remote resets have identical permission bits.
    os.chmod(work_root, 0o750)
    return resolved


def create_database(database_path: Path, seed: dict[str, Any]) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(SCHEMA_SQL)
        connection.executemany(
            "INSERT INTO meta(key, value) VALUES (:key, :value)", seed["meta"]
        )
        connection.executemany(
            """INSERT INTO users(user_id, display_name, status)
               VALUES (:user_id, :display_name, :status)""",
            seed["users"],
        )
        connection.executemany(
            """INSERT INTO hotels(
                   hotel_id, name, city, district, breakfast_included,
                   non_smoking_family_room, nightly_rate_cny
               ) VALUES (
                   :hotel_id, :name, :city, :district, :breakfast_included,
                   :non_smoking_family_room, :nightly_rate_cny
               )""",
            seed["hotels"],
        )
        inventory_rows = [
            {
                "hotel_id": hotel["hotel_id"],
                "stay_date": stay_date,
                "room_type": seed["room_type"],
                "total_rooms": seed["initial_rooms_per_hotel_date"],
                "available_rooms": seed["initial_rooms_per_hotel_date"],
            }
            for hotel in seed["hotels"]
            for stay_date in seed["inventory_dates"]
        ]
        connection.executemany(
            """INSERT INTO inventory(
                   hotel_id, stay_date, room_type, total_rooms, available_rooms
               ) VALUES (
                   :hotel_id, :stay_date, :room_type, :total_rooms, :available_rooms
               )""",
            inventory_rows,
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError("generated database failed integrity check")
    finally:
        connection.close()
    os.chmod(database_path, 0o660)


def reset(work_root: Path, allowed_parent: Path) -> dict[str, Any]:
    resolved = require_fresh_directory(work_root, allowed_parent)
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    agent_workspace = resolved / "agent_workspace"
    state_dir = resolved / "state"
    agent_workspace.mkdir(mode=0o750)
    state_dir.mkdir(mode=0o750)
    os.chmod(agent_workspace, 0o750)
    os.chmod(state_dir, 0o750)
    for destination_name, source in AGENT_FILES.items():
        destination = agent_workspace / destination_name
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o440)
    database_path = state_dir / "hotel_booking.db"
    create_database(database_path, seed)

    logical_state = logical_database_state(database_path)
    workspace_manifest = {
        "schema_version": "nami_work_case16_runtime_manifest_v1",
        "agent_visible_entries": [
            {
                "path": f"agent_workspace/{name}",
                "sha256": file_sha256(agent_workspace / name),
            }
            for name in sorted(AGENT_FILES)
        ],
        "controller_state_entries": [
            {
                "path": "state/hotel_booking.db",
                "logical_state_sha256": hashlib.sha256(
                    canonical_bytes(logical_state)
                ).hexdigest(),
            }
        ],
        "agent_hidden_components": ["state", "oracle", "verifier", "tests"],
    }
    return {
        "status": "reset",
        "work_root": str(resolved),
        "initial_state_sha256": hashlib.sha256(
            canonical_bytes(logical_state)
        ).hexdigest(),
        "runtime_manifest": workspace_manifest,
        "runtime_manifest_sha256": hashlib.sha256(
            canonical_bytes(workspace_manifest)
        ).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--allowed-parent", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = reset(args.work_root, args.allowed_parent)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"status": "invalid", "error": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
