#!/usr/bin/env python3
"""Deterministic SQLite state helpers for case_15."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


TABLE_COLUMNS = {
    "products": (
        "product_id",
        "name",
        "price_cents",
        "rating_x10",
        "inventory",
    ),
    "variants": ("product_id", "size", "color", "active"),
    "users": ("user_id", "display_name"),
    "cart_items": ("user_id", "product_id", "quantity"),
    "orders": ("order_id", "user_id", "status", "total_cents"),
    "settings": ("key", "value"),
    "audit_log": (
        "event_id",
        "event_type",
        "user_id",
        "product_id",
        "quantity",
        "event_time",
    ),
}


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("fixture must be a JSON object")
    return value


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def populate_database(
    connection: sqlite3.Connection,
    catalog: dict[str, Any],
    seed: dict[str, Any],
) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode = DELETE;
        PRAGMA synchronous = FULL;
        CREATE TABLE products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
            rating_x10 INTEGER NOT NULL CHECK(rating_x10 BETWEEN 0 AND 50),
            inventory INTEGER NOT NULL CHECK(inventory >= 0)
        );
        CREATE TABLE variants (
            product_id TEXT NOT NULL REFERENCES products(product_id),
            size TEXT NOT NULL,
            color TEXT NOT NULL,
            active INTEGER NOT NULL CHECK(active IN (0, 1)),
            PRIMARY KEY(product_id, size, color)
        );
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL
        );
        CREATE TABLE cart_items (
            user_id TEXT NOT NULL REFERENCES users(user_id),
            product_id TEXT NOT NULL REFERENCES products(product_id),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            PRIMARY KEY(user_id, product_id)
        );
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            status TEXT NOT NULL,
            total_cents INTEGER NOT NULL CHECK(total_cents >= 0)
        );
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE audit_log (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            event_time TEXT NOT NULL
        );
        """
    )
    for product in catalog["products"]:
        connection.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
            (
                product["product_id"],
                product["name"],
                product["price_cents"],
                product["rating_x10"],
                product["inventory"],
            ),
        )
        for variant in product["variants"]:
            connection.execute(
                "INSERT INTO variants VALUES (?, ?, ?, ?)",
                (
                    product["product_id"],
                    variant["size"],
                    variant["color"],
                    int(bool(variant["active"])),
                ),
            )
    for user in seed["users"]:
        connection.execute(
            "INSERT INTO users VALUES (?, ?)",
            (user["user_id"], user["display_name"]),
        )
    for item in seed["cart_items"]:
        connection.execute(
            "INSERT INTO cart_items VALUES (?, ?, ?)",
            (item["user_id"], item["product_id"], item["quantity"]),
        )
    for order in seed["orders"]:
        connection.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (
                order["order_id"],
                order["user_id"],
                order["status"],
                order["total_cents"],
            ),
        )
    for setting in seed["settings"]:
        connection.execute(
            "INSERT INTO settings VALUES (?, ?)",
            (setting["key"], setting["value"]),
        )
    connection.commit()


def create_database(
    db_path: str | Path,
    catalog_path: str | Path,
    seed_path: str | Path,
) -> None:
    target = Path(db_path)
    for suffix in ("", "-shm", "-wal", "-journal"):
        candidate = Path(str(target) + suffix)
        if candidate.exists():
            candidate.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    with connect(target) as connection:
        populate_database(connection, load_json(catalog_path), load_json(seed_path))


def canonical_state(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    state: dict[str, list[dict[str, Any]]] = {}
    for table, columns in TABLE_COLUMNS.items():
        order = ", ".join(columns)
        rows = connection.execute(
            f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order}"
        ).fetchall()
        state[table] = [{column: row[column] for column in columns} for row in rows]
    return state


def state_hash(connection: sqlite3.Connection) -> str:
    encoded = json.dumps(
        canonical_state(connection),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def state_hash_path(db_path: str | Path) -> str:
    with connect(db_path) as connection:
        return state_hash(connection)


def derive_eligible_products(
    catalog: dict[str, Any], constraints: dict[str, Any]
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for product in catalog["products"]:
        matching_variant = any(
            variant["active"]
            and variant["size"] == constraints["required_size"]
            and variant["color"] == constraints["required_color"]
            for variant in product["variants"]
        )
        if not matching_variant:
            continue
        if product["rating_x10"] < constraints["minimum_rating_x10"]:
            continue
        if product["price_cents"] > constraints["maximum_price_cents"]:
            continue
        if constraints["require_in_stock"] and product["inventory"] < 1:
            continue
        eligible.append(product)
    return sorted(eligible, key=lambda item: (item["price_cents"], item["product_id"]))


def unique_lowest_product(
    catalog: dict[str, Any], constraints: dict[str, Any]
) -> dict[str, Any]:
    eligible = derive_eligible_products(catalog, constraints)
    if not eligible:
        raise ValueError("no eligible product")
    minimum = eligible[0]["price_cents"]
    tied = [item for item in eligible if item["price_cents"] == minimum]
    if len(tied) != 1:
        raise ValueError("lowest eligible product is not unique")
    return tied[0]
