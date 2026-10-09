#!/usr/bin/env python3
"""Build the deterministic, fully synthetic SQLite fixture for case_09."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE contacts (
    contact_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    active INTEGER NOT NULL CHECK (active IN (0, 1))
);
CREATE TABLE fault_rules (
    idempotency_key TEXT PRIMARY KEY,
    error_code INTEGER NOT NULL,
    fail_count INTEGER NOT NULL CHECK (fail_count >= 1)
);
CREATE TABLE protected_policy (
    policy_key TEXT PRIMARY KEY,
    policy_value TEXT NOT NULL
);
CREATE TABLE requests (
    request_id TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL REFERENCES contacts(contact_id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    memo TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status = 'pending'),
    created_at TEXT NOT NULL
);
CREATE TABLE fault_consumptions (
    idempotency_key TEXT PRIMARY KEY REFERENCES fault_rules(idempotency_key),
    consumed_count INTEGER NOT NULL CHECK (consumed_count >= 1)
);
"""

CONTACTS = (
    ("c_001", "Aurora Studio", "ops@aurora.example", "east", 1),
    ("c_002", "Blue Harbor", "hello@blueharbor.example", "west", 1),
    ("c_003", "Cedar Lab", "desk@cedarlab.example", "north", 0),
    ("c_004", "Delta Works", "team@deltaworks.example", "east", 1),
    ("c_005", "Ember Cafe", "contact@embercafe.example", "south", 1),
)

FAULT_RULES = (
    ("idem_retryalpha", -32001, 1),
    ("idem_retrybravo", -32001, 1),
)

POLICY = (
    ("currency", "CNY"),
    ("max_amount_cents", "500000"),
    ("policy_version", "2026-07-case09-v1"),
)


def build(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output)
    try:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO contacts VALUES (?, ?, ?, ?, ?)", CONTACTS)
        connection.executemany("INSERT INTO fault_rules VALUES (?, ?, ?)", FAULT_RULES)
        connection.executemany("INSERT INTO protected_policy VALUES (?, ?)", POLICY)
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
