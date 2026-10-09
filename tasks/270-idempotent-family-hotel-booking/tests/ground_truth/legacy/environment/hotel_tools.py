#!/usr/bin/env python3
"""Deterministic structured tools for the synthetic hotel state machine."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


FIXED_TIME = "2026-07-20T09:00:00+08:00"
MAX_REQUEST_BYTES = 64 * 1024
ALLOWED_BOOKING_REQUEST = {
    "request_id": "REQ-NW16-001",
    "user_id": "CUS-042",
    "hotel_id": "H-CJ-002",
    "check_in": "2026-11-18",
    "check_out": "2026-11-21",
    "adults": 2,
    "children": 1,
    "room_type": "family_standard",
}


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def strict_object(payload: Any, required: set[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ToolError("invalid_request", "request must be an object")
    keys = set(payload)
    if keys != required:
        raise ToolError("invalid_request", "request fields do not match schema")
    return payload


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ToolError("invalid_request", "duplicate JSON object key")
        result[key] = value
    return result


def date_range(check_in: Any, check_out: Any) -> list[str]:
    if not isinstance(check_in, str) or not isinstance(check_out, str):
        raise ToolError("invalid_dates", "dates must be ISO strings")
    try:
        start = date.fromisoformat(check_in)
        end = date.fromisoformat(check_out)
    except ValueError as exc:
        raise ToolError("invalid_dates", "dates must be valid ISO dates") from exc
    if start >= end or (end - start).days > 14:
        raise ToolError("invalid_dates", "stay must be between one and fourteen nights")
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days)]


def database_path(work_root: Path) -> Path:
    if work_root.is_symlink() or not work_root.is_dir():
        raise ToolError("invalid_state", "work root must not be a symbolic link")
    resolved = work_root.resolve(strict=True)
    state = resolved / "state"
    candidate = state / "hotel_booking.db"
    if state.is_symlink() or not state.is_dir() or candidate.is_symlink() or not candidate.is_file():
        raise ToolError("invalid_state", "booking database is missing")
    metadata = os.stat(candidate, follow_symlinks=False)
    if metadata.st_nlink != 1 or metadata.st_size > 8 * 1024 * 1024:
        raise ToolError("invalid_state", "booking database violates resource contract")
    return candidate


def connect(work_root: Path, *, read_only: bool) -> sqlite3.Connection:
    path = database_path(work_root)
    if read_only:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 3000")
    return connection


def require_party(adults: Any, children: Any) -> tuple[int, int]:
    if isinstance(adults, bool) or not isinstance(adults, int) or not 1 <= adults <= 6:
        raise ToolError("invalid_party", "adults must be between 1 and 6")
    if isinstance(children, bool) or not isinstance(children, int) or not 0 <= children <= 4:
        raise ToolError("invalid_party", "children must be between 0 and 4")
    if adults + children > 4:
        raise ToolError("capacity_exceeded", "family_standard capacity is four")
    return adults, children


def search_hotel_inventory(work_root: Path, payload: Any) -> dict[str, Any]:
    request = strict_object(
        payload,
        {
            "city",
            "district",
            "check_in",
            "check_out",
            "adults",
            "children",
            "room_type",
            "breakfast_required",
            "non_smoking_required",
            "max_nightly_rate_cny",
        },
    )
    nights = date_range(request["check_in"], request["check_out"])
    require_party(request["adults"], request["children"])
    if request["room_type"] != "family_standard":
        raise ToolError("unsupported_room_type", "room type is not available")
    for field in ("city", "district"):
        if not isinstance(request[field], str) or not request[field]:
            raise ToolError("invalid_request", f"{field} must be a non-empty string")
    if not isinstance(request["breakfast_required"], bool) or not isinstance(
        request["non_smoking_required"], bool
    ):
        raise ToolError("invalid_request", "facility filters must be boolean")
    max_rate = request["max_nightly_rate_cny"]
    if isinstance(max_rate, bool) or not isinstance(max_rate, int) or max_rate <= 0:
        raise ToolError("invalid_request", "max rate must be a positive integer")

    connection = connect(work_root, read_only=True)
    try:
        hotel_rows = connection.execute(
            """SELECT hotel_id, name, city, district, breakfast_included,
                      non_smoking_family_room, nightly_rate_cny
               FROM hotels
               WHERE city = ? AND district = ? AND nightly_rate_cny <= ?
               ORDER BY nightly_rate_cny, hotel_id""",
            (request["city"], request["district"], max_rate),
        ).fetchall()
        candidates = []
        for hotel in hotel_rows:
            if request["breakfast_required"] and hotel["breakfast_included"] != 1:
                continue
            if request["non_smoking_required"] and hotel["non_smoking_family_room"] != 1:
                continue
            placeholders = ",".join("?" for _ in nights)
            inventory = connection.execute(
                f"""SELECT stay_date, available_rooms
                    FROM inventory
                    WHERE hotel_id = ? AND room_type = ?
                      AND stay_date IN ({placeholders})
                    ORDER BY stay_date""",
                (hotel["hotel_id"], request["room_type"], *nights),
            ).fetchall()
            if len(inventory) != len(nights) or [row["stay_date"] for row in inventory] != nights:
                continue
            minimum_available = min(row["available_rooms"] for row in inventory)
            if minimum_available < 1:
                continue
            candidates.append(
                {
                    "hotel_id": hotel["hotel_id"],
                    "name": hotel["name"],
                    "city": hotel["city"],
                    "district": hotel["district"],
                    "breakfast_included": bool(hotel["breakfast_included"]),
                    "non_smoking_family_room": bool(hotel["non_smoking_family_room"]),
                    "nightly_rate_cny": hotel["nightly_rate_cny"],
                    "nights": len(nights),
                    "minimum_available_rooms": minimum_available,
                    "total_cny": hotel["nightly_rate_cny"] * len(nights),
                }
            )
        return {"status": "ok", "candidates": candidates, "candidate_count": len(candidates)}
    finally:
        connection.close()


def booking_record(connection: sqlite3.Connection, booking_id: str) -> dict[str, Any]:
    row = connection.execute(
        """SELECT booking_id, request_id, user_id, hotel_id, check_in, check_out,
                  adults, children, room_type, status, total_cny, created_at
           FROM bookings WHERE booking_id = ?""",
        (booking_id,),
    ).fetchone()
    if row is None:
        raise ToolError("booking_not_found", "booking does not exist")
    nights = [
        item[0]
        for item in connection.execute(
            "SELECT stay_date FROM booking_nights WHERE booking_id = ? ORDER BY stay_date",
            (booking_id,),
        ).fetchall()
    ]
    result = dict(row)
    result["stay_dates"] = nights
    return result


def create_hotel_booking(work_root: Path, payload: Any) -> dict[str, Any]:
    request = strict_object(
        payload,
        {"request_id", "user_id", "hotel_id", "check_in", "check_out", "adults", "children", "room_type"},
    )
    nights = date_range(request["check_in"], request["check_out"])
    require_party(request["adults"], request["children"])
    if request["room_type"] != "family_standard":
        raise ToolError("unsupported_room_type", "room type is not available")
    for field in ("request_id", "user_id", "hotel_id"):
        if not isinstance(request[field], str) or not request[field]:
            raise ToolError("invalid_request", f"{field} must be a non-empty string")
    if request != ALLOWED_BOOKING_REQUEST:
        raise ToolError("permission_denied", "booking request is outside the case permission scope")

    connection = connect(work_root, read_only=False)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT booking_id FROM bookings WHERE request_id = ?", (request["request_id"],)
        ).fetchone()
        if existing is not None:
            record = booking_record(connection, existing["booking_id"])
            connection.execute("COMMIT")
            return {"status": "ok", "idempotent_replay": True, "booking": record}

        user = connection.execute(
            "SELECT status FROM users WHERE user_id = ?", (request["user_id"],)
        ).fetchone()
        if user is None or user["status"] != "active":
            raise ToolError("user_unavailable", "user is missing or disabled")
        hotel = connection.execute(
            "SELECT nightly_rate_cny FROM hotels WHERE hotel_id = ?", (request["hotel_id"],)
        ).fetchone()
        if hotel is None:
            raise ToolError("hotel_not_found", "hotel does not exist")
        overlapping = connection.execute(
            """SELECT booking_id FROM bookings
               WHERE user_id = ? AND status = 'confirmed'
                 AND check_in < ? AND check_out > ?""",
            (request["user_id"], request["check_out"], request["check_in"]),
        ).fetchone()
        if overlapping is not None:
            raise ToolError("duplicate_stay", "user already has an overlapping booking")

        for stay_date in nights:
            inventory = connection.execute(
                """SELECT available_rooms FROM inventory
                   WHERE hotel_id = ? AND stay_date = ? AND room_type = ?""",
                (request["hotel_id"], stay_date, request["room_type"]),
            ).fetchone()
            if inventory is None or inventory["available_rooms"] < 1:
                raise ToolError("inventory_unavailable", "one or more nights are unavailable")

        booking_count = connection.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        booking_id = f"BKG-NW16-{booking_count + 1:03d}"
        total_cny = hotel["nightly_rate_cny"] * len(nights)
        connection.execute(
            """INSERT INTO bookings(
                   booking_id, request_id, user_id, hotel_id, check_in, check_out,
                   adults, children, room_type, status, total_cny, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)""",
            (
                booking_id,
                request["request_id"],
                request["user_id"],
                request["hotel_id"],
                request["check_in"],
                request["check_out"],
                request["adults"],
                request["children"],
                request["room_type"],
                total_cny,
                FIXED_TIME,
            ),
        )
        for stay_date in nights:
            cursor = connection.execute(
                """UPDATE inventory SET available_rooms = available_rooms - 1
                   WHERE hotel_id = ? AND stay_date = ? AND room_type = ?
                     AND available_rooms > 0""",
                (request["hotel_id"], stay_date, request["room_type"]),
            )
            if cursor.rowcount != 1:
                raise ToolError("inventory_conflict", "inventory changed during booking")
            connection.execute(
                "INSERT INTO booking_nights(booking_id, stay_date) VALUES (?, ?)",
                (booking_id, stay_date),
            )
        audit_payload = json.dumps(
            {
                "check_in": request["check_in"],
                "check_out": request["check_out"],
                "hotel_id": request["hotel_id"],
                "request_id": request["request_id"],
                "user_id": request["user_id"],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            """INSERT INTO audit_events(event_id, event_type, object_id, payload_json, created_at)
               VALUES (1, 'booking_created', ?, ?, ?)""",
            (booking_id, audit_payload, FIXED_TIME),
        )
        connection.execute("COMMIT")
        return {
            "status": "ok",
            "idempotent_replay": False,
            "booking": booking_record(connection, booking_id),
        }
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def get_hotel_booking(work_root: Path, payload: Any) -> dict[str, Any]:
    request = strict_object(payload, {"booking_id"})
    if not isinstance(request["booking_id"], str) or not request["booking_id"]:
        raise ToolError("invalid_request", "booking_id must be a non-empty string")
    connection = connect(work_root, read_only=True)
    try:
        record = booking_record(connection, request["booking_id"])
        if record["request_id"] != ALLOWED_BOOKING_REQUEST["request_id"]:
            raise ToolError("permission_denied", "booking is outside the case permission scope")
        return {"status": "ok", "booking": record}
    finally:
        connection.close()


TOOLS = {
    "search_hotel_inventory": search_hotel_inventory,
    "create_hotel_booking": create_hotel_booking,
    "get_hotel_booking": get_hotel_booking,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--tool", choices=sorted(TOOLS), required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ToolError("invalid_request", "request exceeds byte limit")
        payload = json.loads(raw, object_pairs_hook=no_duplicate_object)
        result = TOOLS[args.tool](args.work_root, payload)
    except ToolError as exc:
        print(json.dumps({"status": "error", "error": {"code": exc.code}}, sort_keys=True))
        return 1
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(json.dumps({"status": "invalid", "error": {"code": type(exc).__name__}}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
