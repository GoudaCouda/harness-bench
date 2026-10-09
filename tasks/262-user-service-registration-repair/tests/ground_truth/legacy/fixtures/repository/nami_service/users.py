from __future__ import annotations

from pathlib import Path

from .db import connect
from .security import verify_password


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


def register_user(
    db_path: str | Path,
    username: str,
    email: str,
    password: str,
    *,
    created_at: str = "2026-07-20T00:00:00Z",
) -> dict[str, object]:
    """Register a user according to TASK.md."""

    raise NotImplementedError("implement the registration contract in TASK.md")
