from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import connect
from .security import hash_password, verify_password


class RegistrationValidationError(ValueError):
    pass


class RegistrationConflict(ValueError):
    pass


def authenticate(db_path: str | Path, identifier: str, password: str) -> bool:
    connection = connect(db_path)
    try:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE",
            (identifier, identifier),
        ).fetchone()
        return bool(row and verify_password(password, row["password_hash"]))
    finally:
        connection.close()


def register_user(
    db_path: str | Path,
    username: str,
    email: str,
    password: str,
    *,
    created_at: str = "2026-07-20T00:00:00Z",
) -> dict[str, object]:
    clean_username = str(username).strip()
    clean_email = str(email).strip().lower()
    connection = connect(db_path)
    try:
        try:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO users(username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (clean_username, clean_email, hash_password(str(password)), created_at),
                )
                connection.execute(
                    "INSERT INTO audit_events(user_id, event_type, created_at) VALUES (?, ?, ?)",
                    (cursor.lastrowid, "user.registered", created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise RegistrationConflict("conflict") from exc
        return {
            "id": int(cursor.lastrowid),
            "username": clean_username,
            "email": clean_email,
            "created_at": created_at,
        }
    finally:
        connection.close()
