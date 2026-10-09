#!/usr/bin/env python3
"""Trusted Unix-socket collaboration sidecar for case_20.

The candidate receives the socket, never the backing SQLite database.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import socketserver
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Any


MAX_REQUEST_BYTES = 16 * 1024
MAX_TOTAL_REQUESTS = 512
MAX_DOWNLOAD_EVENTS = 32
MAX_REMINDER_EVENTS = 12
MAX_DESTINATION_BYTES = 240
MAX_COMPONENT_BYTES = 96
SOCKET_TIMEOUT_SECONDS = 3.0
ALLOWED_CHANNEL = "project-materials"


def list_messages(database: Path, channel: str) -> dict[str, Any]:
    if channel != ALLOWED_CHANNEL:
        raise ValueError("channel is outside the allowed scope")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT m.message_id, m.sender_id, p.name AS sender_name, m.channel,
                          m.sent_at, m.text,
                          (SELECT count(*) FROM attachments a WHERE a.message_id=m.message_id) AS attachment_count
                   FROM messages m JOIN people p ON p.person_id=m.sender_id
                   WHERE m.channel=? ORDER BY m.sent_at, m.message_id""",
                (channel,),
            )
        ]
    finally:
        connection.close()
    return {"ok": True, "messages": rows}


def list_attachments(database: Path, message_id: str) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT a.attachment_id, a.message_id, a.owner_id, p.name AS owner_name,
                          a.material_type, a.original_filename, a.replaces_attachment_id,
                          a.sha256, a.size_bytes, m.sent_at
                   FROM attachments a
                   JOIN messages m ON m.message_id=a.message_id
                   JOIN people p ON p.person_id=a.owner_id
                   WHERE a.message_id=? AND m.channel=? ORDER BY a.attachment_id""",
                (message_id, ALLOWED_CHANNEL),
            )
        ]
    finally:
        connection.close()
    return {"ok": True, "attachments": rows}


def validate_destination(
    value: Any,
    owner_id: str,
    material_type: str,
    original_filename: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError("destination must be a string")
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or "//" in value
        or value.endswith("/")
        or len(value.encode("utf-8")) > MAX_DESTINATION_BYTES
    ):
        raise ValueError("destination encoding is invalid")
    pure = PurePosixPath(value)
    if pure.is_absolute() or len(pure.parts) != 4 or pure.parts[0] != "archive":
        raise ValueError("destination scope is invalid")
    if any(part in {"", ".", ".."} or len(part.encode("utf-8")) > MAX_COMPONENT_BYTES for part in pure.parts):
        raise ValueError("destination component is invalid")
    if pure.parts[1:] != (owner_id, material_type, original_filename):
        raise ValueError("destination must preserve owner, material type, and filename")
    return pure.as_posix()


def reserve_action_slot(connection: sqlite3.Connection, table: str, maximum: int) -> None:
    count = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    if count >= maximum:
        raise ValueError("action quota exceeded")


def download_attachment(database: Path, attachment_id: str, destination: Any) -> dict[str, Any]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """SELECT content, sha256, original_filename, owner_id, material_type
               FROM attachments WHERE attachment_id=?""",
            (attachment_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown attachment")
        logical = validate_destination(
            destination,
            row["owner_id"],
            row["material_type"],
            row["original_filename"],
        )
        fixed_time = connection.execute(
            "SELECT value FROM metadata WHERE key='fixed_time'"
        ).fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        reserve_action_slot(connection, "download_events", MAX_DOWNLOAD_EVENTS)
        connection.execute(
            "INSERT INTO download_events(attachment_id, destination, occurred_at) VALUES (?, ?, ?)",
            (attachment_id, logical, fixed_time),
        )
        connection.commit()
        return {
            "ok": True,
            "attachment_id": attachment_id,
            "destination": logical,
            "sha256": row["sha256"],
            "content_base64": base64.b64encode(row["content"]).decode("ascii"),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def send_reminder(database: Path, recipient_id: str, body: str) -> dict[str, Any]:
    if not isinstance(body, str) or not body or len(body) > 500 or "\n" in body:
        raise ValueError("invalid body")
    connection = sqlite3.connect(database)
    try:
        row = connection.execute(
            "SELECT is_roster_member FROM people WHERE person_id=?", (recipient_id,)
        ).fetchone()
        if row is None or row[0] != 1:
            raise ValueError("invalid recipient")
        fixed_time = connection.execute(
            "SELECT value FROM metadata WHERE key='fixed_time'"
        ).fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        reserve_action_slot(connection, "reminder_events", MAX_REMINDER_EVENTS)
        cursor = connection.execute(
            "INSERT INTO reminder_events(recipient_id, body, sent_at) VALUES (?, ?, ?)",
            (recipient_id, body, fixed_time),
        )
        connection.commit()
        return {"ok": True, "event_id": cursor.lastrowid, "recipient_id": recipient_id}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def dispatch(database: Path, request: Any) -> dict[str, Any]:
    if not isinstance(request, dict) or not isinstance(request.get("operation"), str):
        raise ValueError("invalid request")
    operation = request["operation"]
    if operation == "list_messages":
        channel = request.get("channel")
        if not isinstance(channel, str):
            raise ValueError("invalid channel")
        return list_messages(database, channel)
    if operation == "list_attachments":
        message_id = request.get("message_id")
        if not isinstance(message_id, str):
            raise ValueError("invalid message_id")
        return list_attachments(database, message_id)
    if operation == "download_attachment":
        attachment_id = request.get("attachment_id")
        if not isinstance(attachment_id, str):
            raise ValueError("invalid attachment_id")
        return download_attachment(database, attachment_id, request.get("destination"))
    if operation == "send_reminder":
        recipient_id = request.get("recipient_id")
        body = request.get("body")
        if not isinstance(recipient_id, str) or not isinstance(body, str):
            raise ValueError("invalid reminder")
        return send_reminder(database, recipient_id, body)
    raise ValueError("unsupported operation")


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.connection.settimeout(SOCKET_TIMEOUT_SECONDS)
        try:
            raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if len(raw) > MAX_REQUEST_BYTES or not raw.endswith(b"\n"):
                response = {"ok": False, "error": "RequestSizeError"}
            elif self.server.request_count >= MAX_TOTAL_REQUESTS:  # type: ignore[attr-defined]
                response = {"ok": False, "error": "RequestQuotaError"}
            else:
                self.server.request_count += 1  # type: ignore[attr-defined]
                request = json.loads(raw.decode("utf-8"))
                response = dispatch(self.server.database, request)  # type: ignore[attr-defined]
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, sqlite3.Error) as exc:
            response = {"ok": False, "error": type(exc).__name__}
        try:
            self.wfile.write(json.dumps(response, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
        except OSError:
            return


class Server(socketserver.UnixStreamServer):
    allow_reuse_address = False

    def __init__(self, socket_path: str, handler: type[Handler], database: Path):
        self.database = database
        self.request_count = 0
        super().__init__(socket_path, handler)


def serve(work_root: Path) -> None:
    work_root = work_root.resolve(strict=True)
    marker = work_root / ".case20_runtime"
    database = work_root / "service_state/collaboration.sqlite"
    if (
        not marker.is_file()
        or marker.is_symlink()
        or marker.read_text(encoding="utf-8") != "case_20\n"
        or not database.is_file()
        or database.is_symlink()
    ):
        raise ValueError("work root is not a valid case_20 runtime")
    socket_path = work_root / "service.sock"
    if socket_path.exists() or socket_path.is_symlink():
        socket_path.unlink()
    server = Server(str(socket_path), Handler, database)
    os.chmod(socket_path, 0o600)

    def stop(_signum: int, _frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        socket_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    serve(args.work_root)


if __name__ == "__main__":
    main()
