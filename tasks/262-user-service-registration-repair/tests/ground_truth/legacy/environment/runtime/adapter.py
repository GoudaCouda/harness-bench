from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


MAX_REQUEST_BYTES = 65_536
MAX_CAPTURE_CHARS = 65_536
RESULT_PREFIX = "CASE08_RESULT "
WORKSPACE = Path("/workspace")


class BoundedText(io.StringIO):
    def write(self, value: str) -> int:
        if self.tell() + len(value) > MAX_CAPTURE_CHARS:
            raise RuntimeError("candidate_python_output_limit")
        return super().write(value)


def read_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request_must_be_object")
    return value


def candidate_module() -> Any:
    sys.path.insert(0, str(WORKSPACE))
    return importlib.import_module("nami_service.users")


def call_candidate(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    if operation == "public_tests":
        completed = subprocess.run(
            [sys.executable, "run_public_tests.py"],
            cwd=WORKSPACE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
            env={
                "HOME": "/nonexistent",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PATH": os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "TMPDIR": "/scratch",
                "TZ": "UTC",
            },
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "output_chars": len(completed.stdout),
        }

    users = candidate_module()
    database = WORKSPACE / "state" / "service.db"
    if operation == "authenticate":
        value = users.authenticate(
            database,
            request.get("identifier"),
            request.get("password"),
        )
        return {"ok": True, "value": bool(value)}
    if operation == "register":
        try:
            value = users.register_user(
                database,
                request.get("username"),
                request.get("email"),
                request.get("password"),
                created_at=request.get("created_at", "2026-07-20T00:00:00Z"),
            )
        except Exception as exc:  # noqa: BLE001 - exception type is the public contract
            return {
                "ok": False,
                "exception_type": type(exc).__name__,
                "message_chars": len(str(exc)),
            }
        if not isinstance(value, dict):
            return {"ok": True, "return_type": type(value).__name__}
        public_value = {
            key: value.get(key)
            for key in ("id", "username", "email", "created_at")
            if key in value
        }
        return {
            "ok": True,
            "return_type": "dict",
            "keys": sorted(value),
            "public_value": public_value,
        }
    raise ValueError("unsupported_operation")


def main() -> int:
    try:
        request = read_request()
        captured_out = BoundedText()
        captured_err = BoundedText()
        with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(
            captured_err
        ):
            payload = call_candidate(request)
        envelope = {
            "adapter_schema": "case08_answer_independent_adapter_v1",
            "candidate_stdout_chars": len(captured_out.getvalue()),
            "candidate_stderr_chars": len(captured_err.getvalue()),
            "payload": payload,
        }
        encoded = RESULT_PREFIX + json.dumps(envelope, sort_keys=True) + "\n"
        os.write(1, encoded.encode("utf-8"))
        return 0
    except BaseException as exc:  # noqa: BLE001 - fail-closed runtime envelope
        envelope = {
            "adapter_schema": "case08_answer_independent_adapter_v1",
            "adapter_error": type(exc).__name__,
            "message_chars": len(str(exc)),
        }
        encoded = RESULT_PREFIX + json.dumps(envelope, sort_keys=True) + "\n"
        os.write(1, encoded.encode("utf-8"))
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
