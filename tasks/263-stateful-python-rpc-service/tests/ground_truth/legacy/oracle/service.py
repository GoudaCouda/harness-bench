#!/usr/bin/env python3
"""Reference implementation for the hidden case_09 protocol checks."""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


TEST_MUTATION = ""
FIXED_CREATED_AT = "2026-07-20T09:00:00Z"
REQUEST_ID_RE = re.compile(r"^req_[a-z0-9]{6,20}$")
CONTACT_ID_RE = re.compile(r"^c_[0-9]{3}$")
IDEMPOTENCY_RE = re.compile(r"^idem_[a-z0-9]{6,24}$")


def rpc_result(request_id: str | int, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def rpc_error(
    request_id: object,
    code: int,
    message: str,
    *,
    name: str,
    retryable: bool,
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
            "data": {"name": name, "retryable": retryable},
        },
    }


def contract_path() -> Path:
    configured = os.environ.get("CASE09_CONTRACT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent.parent / "protocol_contract.json"


def load_catalog() -> list[dict[str, object]]:
    document = json.loads(contract_path().read_text(encoding="utf-8"))
    catalog = document["tool_catalog"]
    if not isinstance(catalog, list):
        raise ValueError("invalid tool catalog")
    copied = json.loads(json.dumps(catalog))
    if TEST_MUTATION == "missing_tool":
        return copied[:1]
    if TEST_MUTATION == "wrong_schema":
        copied[0]["inputSchema"]["properties"]["limit"]["maximum"] = 9
    return copied


def paths() -> tuple[Path, Path]:
    seed_value = os.environ.get("CASE09_SEED_DB")
    state_value = os.environ.get("CASE09_STATE_DB")
    if not seed_value or not state_value:
        raise ValueError("CASE09_SEED_DB and CASE09_STATE_DB are required")
    return Path(seed_value), Path(state_value)


def initialize_state() -> Path:
    seed, state = paths()
    if not seed.is_file() or seed.is_symlink():
        raise ValueError("seed database is unavailable")
    if state.is_symlink():
        raise ValueError("state database cannot be a symbolic link")
    if not state.exists():
        state.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, state)
    if TEST_MUTATION == "protected_mutation":
        with sqlite3.connect(state) as connection:
            connection.execute(
                "UPDATE protected_policy SET policy_value = 'tampered' WHERE policy_key = 'currency'"
            )
            connection.commit()
    if TEST_MUTATION == "process_leak":
        subprocess.Popen(
            ["sleep", "120"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return state


def valid_request_id(value: object) -> bool:
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def exact_keys(value: dict[str, Any], required: set[str], optional: set[str] | None = None) -> bool:
    allowed = required | (optional or set())
    return required <= set(value) and set(value) <= allowed


def validate_search(arguments: object) -> dict[str, object] | None:
    if not isinstance(arguments, dict) or not exact_keys(arguments, {"query"}, {"limit"}):
        return None
    query = arguments.get("query")
    limit = arguments.get("limit", 5)
    if not isinstance(query, str) or not 1 <= len(query) <= 80:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
        return None
    return {"query": query, "limit": limit}


def validate_create(arguments: object) -> dict[str, object] | None:
    required = {"request_id", "contact_id", "amount_cents", "memo", "idempotency_key"}
    if not isinstance(arguments, dict) or not exact_keys(arguments, required):
        return None
    request_id = arguments.get("request_id")
    contact_id = arguments.get("contact_id")
    amount = arguments.get("amount_cents")
    memo = arguments.get("memo")
    key = arguments.get("idempotency_key")
    if not isinstance(request_id, str) or REQUEST_ID_RE.fullmatch(request_id) is None:
        return None
    if not isinstance(contact_id, str) or CONTACT_ID_RE.fullmatch(contact_id) is None:
        return None
    if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= 500000:
        return None
    if not isinstance(memo, str) or not 1 <= len(memo) <= 200:
        return None
    if not isinstance(key, str) or IDEMPOTENCY_RE.fullmatch(key) is None:
        return None
    return {
        "request_id": request_id,
        "contact_id": contact_id,
        "amount_cents": amount,
        "memo": memo,
        "idempotency_key": key,
    }


def request_object(row: sqlite3.Row) -> dict[str, object]:
    return {
        "request_id": row["request_id"],
        "contact_id": row["contact_id"],
        "amount_cents": row["amount_cents"],
        "memo": row["memo"],
        "idempotency_key": row["idempotency_key"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def search_contacts(state: Path, arguments: dict[str, object]) -> dict[str, object]:
    query = str(arguments["query"]).casefold()
    pattern = f"%{query}%"
    with sqlite3.connect(state) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT contact_id, display_name, email, region
            FROM contacts
            WHERE active = 1 AND (lower(display_name) LIKE ? OR lower(email) LIKE ?)
            ORDER BY contact_id
            LIMIT ?
            """,
            (pattern, pattern, arguments["limit"]),
        ).fetchall()
    items = [dict(row) for row in rows]
    return {"items": items, "count": len(items)}


def create_request(
    request_id: str | int,
    state: Path,
    arguments: dict[str, object],
) -> dict[str, object]:
    connection = sqlite3.connect(state)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM requests WHERE idempotency_key = ?",
            (arguments["idempotency_key"],),
        ).fetchone()
        if existing is not None:
            expected = {
                "request_id": arguments["request_id"],
                "contact_id": arguments["contact_id"],
                "amount_cents": arguments["amount_cents"],
                "memo": arguments["memo"],
                "idempotency_key": arguments["idempotency_key"],
            }
            actual = {name: existing[name] for name in expected}
            if actual != expected:
                connection.rollback()
                return rpc_error(
                    request_id,
                    -32011,
                    "idempotency key conflicts with an existing request",
                    name="idempotency_conflict",
                    retryable=False,
                )
            connection.commit()
            return rpc_result(request_id, {"request": request_object(existing)})

        conflicting_id = connection.execute(
            "SELECT 1 FROM requests WHERE request_id = ?", (arguments["request_id"],)
        ).fetchone()
        if conflicting_id is not None:
            connection.rollback()
            return rpc_error(
                request_id,
                -32011,
                "request identifier conflicts with an existing request",
                name="idempotency_conflict",
                retryable=False,
            )

        contact = connection.execute(
            "SELECT active FROM contacts WHERE contact_id = ?", (arguments["contact_id"],)
        ).fetchone()
        if contact is None or contact["active"] != 1:
            if TEST_MUTATION == "inactive_write":
                connection.execute(
                    "INSERT OR REPLACE INTO protected_policy VALUES ('unauthorized_request', 'written')"
                )
                connection.commit()
            else:
                connection.rollback()
            return rpc_error(
                request_id,
                -32010,
                "contact is unavailable",
                name="contact_inactive",
                retryable=False,
            )

        rule = connection.execute(
            "SELECT error_code, fail_count FROM fault_rules WHERE idempotency_key = ?",
            (arguments["idempotency_key"],),
        ).fetchone()
        consumed = connection.execute(
            "SELECT consumed_count FROM fault_consumptions WHERE idempotency_key = ?",
            (arguments["idempotency_key"],),
        ).fetchone()
        consumed_count = 0 if consumed is None else consumed["consumed_count"]
        if rule is not None and consumed_count < rule["fail_count"]:
            if TEST_MUTATION == "bad_transient":
                connection.rollback()
                return rpc_error(
                    request_id,
                    -32603,
                    "fault was not classified as retryable",
                    name="internal_error",
                    retryable=False,
                )
            connection.execute(
                """
                INSERT INTO fault_consumptions(idempotency_key, consumed_count)
                VALUES (?, 1)
                ON CONFLICT(idempotency_key)
                DO UPDATE SET consumed_count = consumed_count + 1
                """,
                (arguments["idempotency_key"],),
            )
            connection.commit()
            return rpc_error(
                request_id,
                -32001,
                "transient capacity limit; retry the same request",
                name="transient_busy",
                retryable=True,
            )

        connection.execute(
            """
            INSERT INTO requests(
                request_id, contact_id, amount_cents, memo,
                idempotency_key, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                arguments["request_id"],
                arguments["contact_id"],
                arguments["amount_cents"],
                arguments["memo"],
                arguments["idempotency_key"],
                FIXED_CREATED_AT,
            ),
        )
        created = connection.execute(
            "SELECT * FROM requests WHERE idempotency_key = ?",
            (arguments["idempotency_key"],),
        ).fetchone()
        connection.commit()
        if created is None:
            raise RuntimeError("created request is missing")
        return rpc_result(request_id, {"request": request_object(created)})
    finally:
        connection.close()


def handle(request: object, state: Path, catalog: list[dict[str, object]]) -> dict[str, object]:
    if not isinstance(request, dict) or not exact_keys(request, {"jsonrpc", "id", "method"}, {"params"}):
        return rpc_error(None, -32600, "invalid request", name="invalid_request", retryable=False)
    request_id = request.get("id")
    if request.get("jsonrpc") != "2.0" or not valid_request_id(request_id) or not isinstance(request.get("method"), str):
        return rpc_error(None, -32600, "invalid request", name="invalid_request", retryable=False)
    method = request["method"]
    params = request.get("params", {})
    if method == "tools/list":
        if params != {}:
            return rpc_error(request_id, -32602, "invalid params", name="invalid_params", retryable=False)
        return rpc_result(request_id, {"tools": catalog})
    if method != "tools/call":
        return rpc_error(request_id, -32601, "method not found", name="method_not_found", retryable=False)
    if not isinstance(params, dict) or not exact_keys(params, {"name", "arguments"}) or not isinstance(params.get("name"), str):
        return rpc_error(request_id, -32602, "invalid params", name="invalid_params", retryable=False)
    name = params["name"]
    if name == "contacts.search":
        arguments = validate_search(params["arguments"])
        if arguments is None:
            return rpc_error(request_id, -32602, "invalid params", name="invalid_params", retryable=False)
        return rpc_result(request_id, search_contacts(state, arguments))
    if name == "requests.create":
        arguments = validate_create(params["arguments"])
        if arguments is None:
            return rpc_error(request_id, -32602, "invalid params", name="invalid_params", retryable=False)
        return create_request(request_id, state, arguments)
    return rpc_error(request_id, -32601, "tool not found", name="method_not_found", retryable=False)


def main() -> int:
    try:
        state = initialize_state()
        catalog = load_catalog()
    except Exception:
        return 2
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError:
            payload = rpc_error(None, -32700, "parse error", name="parse_error", retryable=False)
        else:
            try:
                payload = handle(request, state, catalog)
            except Exception:
                request_id = request.get("id") if isinstance(request, dict) else None
                payload = rpc_error(request_id, -32603, "internal error", name="internal_error", retryable=False)
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
