#!/usr/bin/env python3
"""Hidden local Unix-socket gateway for the case_16 structured tools."""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from typing import Any

from hotel_tools import TOOLS, ToolError


MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024


class RequestError(ValueError):
    """A candidate-controlled request is malformed."""


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RequestError("duplicate JSON object key")
        result[key] = value
    return result


def receive_request(connection: socket.socket) -> dict[str, Any]:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = connection.recv(min(65536, MAX_REQUEST_BYTES + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_REQUEST_BYTES:
            raise RequestError("request exceeds byte limit")
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    line, separator, remainder = raw.partition(b"\n")
    if not separator or remainder:
        raise RequestError("invalid request frame")
    try:
        request = json.loads(line, object_pairs_hook=no_duplicate_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError("request is not valid JSON") from exc
    if not isinstance(request, dict) or set(request) != {"tool", "arguments"}:
        raise RequestError("request envelope does not match schema")
    if request["tool"] not in TOOLS or not isinstance(request["arguments"], dict):
        raise RequestError("tool or arguments are invalid")
    return request


def response_bytes(payload: dict[str, Any]) -> bytes:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    if len(rendered) > MAX_RESPONSE_BYTES:
        return b'{"error":{"code":"response_too_large"},"status":"unavailable"}\n'
    return rendered


def handle(connection: socket.socket, work_root: Path) -> None:
    try:
        request = receive_request(connection)
        payload = TOOLS[request["tool"]](work_root, request["arguments"])
    except (RequestError, ToolError) as exc:
        code = exc.code if isinstance(exc, ToolError) else "invalid_request"
        payload = {"status": "error", "error": {"code": code}}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {"status": "unavailable", "error": {"code": type(exc).__name__}}
    connection.sendall(response_bytes(payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--socket-path", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--idle-timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    if args.max_requests < 1 or args.max_requests > 100:
        raise SystemExit("max requests must be between 1 and 100")
    if args.idle_timeout_seconds < 1 or args.idle_timeout_seconds > 7260:
        raise SystemExit("idle timeout must be between 1 and 7260 seconds")
    socket_parent = args.socket_path.parent
    if socket_parent.is_symlink() or not socket_parent.is_dir():
        raise SystemExit("socket parent must be an existing real directory")
    if args.socket_path.exists() or args.socket_path.is_symlink():
        raise SystemExit("socket path must not already exist")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(args.socket_path))
        os.chmod(args.socket_path, 0o660)
        listener.listen(4)
        listener.settimeout(float(args.idle_timeout_seconds))
        for _ in range(args.max_requests):
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(10.0)
                handle(connection, args.work_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
