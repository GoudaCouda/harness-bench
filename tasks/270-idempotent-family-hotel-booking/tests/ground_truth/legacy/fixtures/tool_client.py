#!/usr/bin/env python3
"""Agent-visible client for the case_16 local structured-tool gateway."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import Any


MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
DEFAULT_SOCKET = "/tool_gateway/hotel.sock"
TOOLS = {
    "create_hotel_booking",
    "get_hotel_booking",
    "search_hotel_inventory",
}


class ClientInputError(ValueError):
    """The candidate supplied a malformed tool request."""


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ClientInputError("duplicate JSON object key")
        result[key] = value
    return result


def read_arguments() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ClientInputError("request exceeds byte limit")
    try:
        value = json.loads(raw, object_pairs_hook=no_duplicate_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClientInputError("request is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ClientInputError("tool arguments must be a JSON object")
    return value


def receive_line(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = connection.recv(min(65536, MAX_RESPONSE_BYTES + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise RuntimeError("tool response exceeds byte limit")
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    line, separator, remainder = raw.partition(b"\n")
    if not separator or remainder:
        raise RuntimeError("tool gateway returned an invalid frame")
    return line


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", choices=sorted(TOOLS), required=True)
    parser.add_argument("--socket", default=DEFAULT_SOCKET)
    args = parser.parse_args()
    try:
        arguments = read_arguments()
    except ClientInputError:
        print(json.dumps({"status": "error", "error": {"code": "invalid_request"}}, sort_keys=True))
        return 1

    request = json.dumps(
        {"tool": args.tool, "arguments": arguments},
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(10.0)
            connection.connect(args.socket)
            connection.sendall(request)
            connection.shutdown(socket.SHUT_WR)
            response = receive_line(connection)
        payload = json.loads(response)
        if not isinstance(payload, dict) or payload.get("status") not in {"ok", "error", "unavailable"}:
            raise RuntimeError("tool gateway returned an invalid response")
    except (OSError, RuntimeError, json.JSONDecodeError):
        print(json.dumps({"status": "unavailable", "error": {"code": "tool_gateway_unavailable"}}, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
