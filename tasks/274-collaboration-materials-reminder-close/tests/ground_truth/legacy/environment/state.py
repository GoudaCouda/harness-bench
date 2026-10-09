#!/usr/bin/env python3
"""Logical state helpers shared by case_20 reset, tools, and trusted checks."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_tree_inventory(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not root.is_dir() or root.is_symlink():
        raise ValueError("tree root must be a real directory")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"symbolic link is forbidden: {relative}")
        if stat.S_ISDIR(mode):
            records.append(
                {"path": relative, "type": "directory", "mode": oct(stat.S_IMODE(mode))}
            )
        elif stat.S_ISREG(mode):
            records.append(
                {
                    "path": relative,
                    "type": "file",
                    "mode": oct(stat.S_IMODE(mode)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        else:
            raise ValueError(f"special file is forbidden: {relative}")
    return records


def load_seed(case_root: Path) -> dict[str, Any]:
    return json.loads((case_root / "fixtures/service_seed.json").read_text(encoding="utf-8"))


def source_projection_from_seed(case_root: Path) -> dict[str, Any]:
    seed = load_seed(case_root)
    attachments = []
    for item in seed["attachments"]:
        path = case_root / "fixtures" / item["fixture_path"]
        payload = path.read_bytes()
        attachments.append(
            {
                **{key: value for key, value in item.items() if key != "fixture_path"},
                "sha256": sha256_bytes(payload),
                "size_bytes": len(payload),
            }
        )
    return {
        "schema_version": seed["schema_version"],
        "fixed_time": seed["fixed_time"],
        "channel": seed["channel"],
        "people": seed["people"],
        "messages": seed["messages"],
        "attachments": attachments,
    }


def build_database(case_root: Path, database: Path) -> None:
    seed = load_seed(case_root)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE people (
              person_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              is_roster_member INTEGER NOT NULL CHECK(is_roster_member IN (0, 1))
            );
            CREATE TABLE messages (
              message_id TEXT PRIMARY KEY,
              sender_id TEXT NOT NULL REFERENCES people(person_id),
              channel TEXT NOT NULL,
              sent_at TEXT NOT NULL,
              text TEXT NOT NULL
            );
            CREATE TABLE attachments (
              attachment_id TEXT PRIMARY KEY,
              message_id TEXT NOT NULL REFERENCES messages(message_id),
              owner_id TEXT NOT NULL REFERENCES people(person_id),
              material_type TEXT NOT NULL,
              original_filename TEXT NOT NULL,
              replaces_attachment_id TEXT,
              content BLOB NOT NULL,
              sha256 TEXT NOT NULL,
              size_bytes INTEGER NOT NULL
            );
            CREATE TABLE download_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              attachment_id TEXT NOT NULL,
              destination TEXT NOT NULL,
              occurred_at TEXT NOT NULL
            );
            CREATE TABLE reminder_events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              recipient_id TEXT NOT NULL,
              body TEXT NOT NULL,
              sent_at TEXT NOT NULL
            );
            """
        )
        source_projection = source_projection_from_seed(case_root)
        metadata = {
            "schema_version": "case20_collaboration_db_v1",
            "fixed_time": seed["fixed_time"],
            "channel": seed["channel"],
            "source_projection_sha256": sha256_bytes(canonical_json_bytes(source_projection)),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", sorted(metadata.items())
        )
        connection.executemany(
            "INSERT INTO people(person_id, name, is_roster_member) VALUES (?, ?, ?)",
            [
                (item["person_id"], item["name"], int(item["is_roster_member"]))
                for item in seed["people"]
            ],
        )
        connection.executemany(
            "INSERT INTO messages(message_id, sender_id, channel, sent_at, text) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    item["message_id"],
                    item["sender_id"],
                    item["channel"],
                    item["sent_at"],
                    item["text"],
                )
                for item in seed["messages"]
            ],
        )
        rows = []
        for item in seed["attachments"]:
            payload = (case_root / "fixtures" / item["fixture_path"]).read_bytes()
            rows.append(
                (
                    item["attachment_id"],
                    item["message_id"],
                    item["owner_id"],
                    item["material_type"],
                    item["original_filename"],
                    item["replaces_attachment_id"],
                    payload,
                    sha256_bytes(payload),
                    len(payload),
                )
            )
        connection.executemany(
            """INSERT INTO attachments(
              attachment_id, message_id, owner_id, material_type, original_filename,
              replaces_attachment_id, content, sha256, size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def source_projection_from_database(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        people = [
            {
                "person_id": row["person_id"],
                "name": row["name"],
                "is_roster_member": bool(row["is_roster_member"]),
            }
            for row in connection.execute(
                "SELECT person_id, name, is_roster_member FROM people ORDER BY rowid"
            )
        ]
        messages = [
            dict(row)
            for row in connection.execute(
                "SELECT message_id, sender_id, channel, sent_at, text FROM messages ORDER BY rowid"
            )
        ]
        attachments = [
            dict(row)
            for row in connection.execute(
                """SELECT attachment_id, message_id, owner_id, material_type,
                          original_filename, replaces_attachment_id, sha256, size_bytes
                   FROM attachments ORDER BY rowid"""
            )
        ]
        return {
            "schema_version": "case20_collaboration_seed_v1",
            "fixed_time": metadata["fixed_time"],
            "channel": metadata["channel"],
            "people": people,
            "messages": messages,
            "attachments": attachments,
        }
    finally:
        connection.close()


def action_projection(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return {
            "downloads": [
                dict(row)
                for row in connection.execute(
                    "SELECT event_id, attachment_id, destination, occurred_at FROM download_events ORDER BY event_id"
                )
            ],
            "reminders": [
                dict(row)
                for row in connection.execute(
                    "SELECT event_id, recipient_id, body, sent_at FROM reminder_events ORDER BY event_id"
                )
            ],
        }
    finally:
        connection.close()


def logical_state(workspace: Path, database: Path) -> dict[str, Any]:
    return {
        "workspace": strict_tree_inventory(workspace),
        "source": source_projection_from_database(database),
        "actions": action_projection(database),
    }


def logical_state_sha256(workspace: Path, database: Path) -> str:
    return sha256_bytes(canonical_json_bytes(logical_state(workspace, database)))


def database_paths_from_environment() -> tuple[Path, Path]:
    workspace_value = os.environ.get("CASE20_WORKSPACE")
    database_value = os.environ.get("CASE20_SERVICE_DB")
    if not workspace_value or not database_value:
        raise ValueError("CASE20_WORKSPACE and CASE20_SERVICE_DB must be explicitly set")
    workspace = Path(workspace_value).resolve(strict=True)
    database = Path(database_value).resolve(strict=True)
    if not workspace.is_dir() or database.is_symlink() or not database.is_file():
        raise ValueError("invalid runtime paths")
    return workspace, database
