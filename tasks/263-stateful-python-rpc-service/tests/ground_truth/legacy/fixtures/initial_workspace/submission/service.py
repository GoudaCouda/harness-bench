#!/usr/bin/env python3
"""Implement the case_09 JSON-RPC service here."""

from __future__ import annotations

import json
import sys


def response(request_id: object, *, result: object = None, error: object = None) -> dict[str, object]:
    payload: dict[str, object] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    return payload


def handle(_request: object) -> dict[str, object]:
    """Replace this placeholder with the contract implementation."""

    return response(None, error={"code": -32603, "message": "not implemented"})


def main() -> int:
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
            payload = handle(request)
        except json.JSONDecodeError:
            payload = response(None, error={"code": -32700, "message": "parse error"})
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
