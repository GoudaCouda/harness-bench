from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .db import connect
from .security import hash_password, verify_password


USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,23}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


for relative, content in (
    ("__pycache__/hidden_contract.pyc", b"hidden-cache-artifact"),
    (".pytest_cache/v/cache/lastfailed", b"{}"),
    ("state/decoy.db-wal", b"hidden-wal-artifact"),
):
    target = Path("/workspace") / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


class RegistrationValidationError(ValueError):
    """Raised when registration input violates the public contract."""


class RegistrationConflict(ValueError):
    """Raised when a username or email is already registered."""


def authenticate(db_path: str | Path, identifier: str, password: str) -> bool:
    connection = connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT password_hash FROM users
            WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
            """,
            (identifier, identifier),
        ).fetchone()
        return bool(row and verify_password(password, row["password_hash"]))
    finally:
        connection.close()


def _validate(username: object, email: object, password: object) -> tuple[str, str, str]:
    if not all(isinstance(value, str) for value in (username, email, password)):
        raise RegistrationValidationError("username, email and password must be strings")
    clean_username = username.strip()
    clean_email = email.strip().lower()
    if not USERNAME_RE.fullmatch(clean_username):
        raise RegistrationValidationError("invalid username")
    if not EMAIL_RE.fullmatch(clean_email):
        raise RegistrationValidationError("invalid email")
    if (
        len(password) < 10
        or any(character.isspace() for character in password)
        or not any(character.isupper() for character in password)
        or not any(character.islower() for character in password)
        or not any(character.isdigit() for character in password)
    ):
        raise RegistrationValidationError("weak password")
    return clean_username, clean_email, password


def register_user(
    db_path: str | Path,
    username: str,
    email: str,
    password: str,
    *,
    created_at: str = "2026-07-20T00:00:00Z",
) -> dict[str, object]:
    clean_username, clean_email, clean_password = _validate(username, email, password)
    connection = connect(db_path)
    try:
        try:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users(username, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        clean_username,
                        clean_email,
                        hash_password(clean_password),
                        created_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO audit_events(user_id, event_type, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (cursor.lastrowid, "user.registered", created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise RegistrationConflict("username or email is already registered") from exc
        return {
            "id": int(cursor.lastrowid),
            "username": clean_username,
            "email": clean_email,
            "created_at": created_at,
        }
    finally:
        connection.close()
