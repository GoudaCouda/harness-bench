from __future__ import annotations

import sqlite3
from pathlib import Path

from .security import hash_password


FIXED_SEED_TIME = "2026-07-20T00:00:00Z"
FIXED_SEED_SALT = bytes.fromhex("00112233445566778899aabbccddeeff")


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path), timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(path)
    try:
        with connection:
            connection.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            cursor = connection.execute(
                """
                INSERT INTO users(username, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "alice",
                    "alice@example.test",
                    hash_password("ExistingPass9", salt=FIXED_SEED_SALT),
                    FIXED_SEED_TIME,
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events(user_id, event_type, created_at)
                VALUES (?, ?, ?)
                """,
                (cursor.lastrowid, "user.seeded", FIXED_SEED_TIME),
            )
    finally:
        connection.close()
