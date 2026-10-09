#!/usr/bin/env python3
"""Capability-addressed Alertmanager control-plane emulator for task 094.

This is deliberately not an Alertmanager daemon. It models only the declared
management surface needed by the task, while the fixed protected validator checks
configuration semantics for the agent, reload path, and grader. Its authoritative
ledger lives in a controller-owned temporary directory, not in either of the
agent's mounts. Successful reloads are bound to the SHA-256 of the candidate
configuration observed at that moment. The first reload returns a transient
503 so that a successful run must demonstrate recovery rather than a
happy-path-only workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _matcher(name: str, value: str) -> dict[str, object]:
    return {
        "name": name,
        "value": value,
        "isRegex": False,
        "isEqual": True,
    }


class RehearsalStore:
    def __init__(
        self,
        state_dir: Path,
        instance_id: str,
        config_path: Path,
        validator: Path,
        validator_sha256: str,
        validator_version: str,
    ) -> None:
        now = _utc_now()
        broad_id = "sil-" + uuid.uuid4().hex
        unrelated_id = "sil-" + uuid.uuid4().hex
        expired_id = "sil-" + uuid.uuid4().hex
        seed_silences = [
            {
                "id": unrelated_id,
                "status": {"state": "active"},
                "matchers": [
                    _matcher("service", "inventory"),
                    _matcher("alertname", "DeployNoise"),
                ],
                "startsAt": _iso_utc(now - timedelta(minutes=5)),
                "endsAt": _iso_utc(now + timedelta(minutes=40)),
                "createdBy": "another-operator",
                "comment": "unrelated local rehearsal",
            },
            {
                "id": expired_id,
                "status": {"state": "expired"},
                "matchers": [_matcher("service", "payments")],
                "startsAt": _iso_utc(now - timedelta(hours=3)),
                "endsAt": _iso_utc(now - timedelta(hours=2)),
                "createdBy": "old-operator",
                "comment": "already expired",
            },
            {
                "id": broad_id,
                "status": {"state": "active"},
                "matchers": [_matcher("service", "payments")],
                "startsAt": _iso_utc(now - timedelta(minutes=20)),
                "endsAt": _iso_utc(now + timedelta(hours=4)),
                "createdBy": "incident-rehearsal",
                "comment": "INC-482 unsafe broad silence",
            },
        ]
        self.lock = threading.RLock()
        self.config_path = config_path.resolve()
        self.validator = validator.resolve()
        self.validator_sha256 = validator_sha256
        self.validator_version = validator_version
        self.state_path = state_dir / "alertmanager-rehearsal-state.json"
        self.state: dict[str, Any] = {
            "schema_version": 1,
            "instance_id": instance_id,
            "service_started_at": _iso_utc(now),
            "snapshot_at": _iso_utc(now),
            "seed_ids": {
                "broad": broad_id,
                "unrelated": unrelated_id,
                "expired": expired_id,
            },
            "seed_silences": seed_silences,
            "silences": json.loads(json.dumps(seed_silences)),
            "events": [],
            "active_config_sha256": None,
            "validator_sha256": validator_sha256,
            "validator_version": validator_version,
            "transient_reload_failures_configured": 1,
            "transient_reload_failures_remaining": 1,
        }
        state_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(state_dir, 0o700)
        self._persist()

    def _persist(self) -> None:
        self.state["snapshot_at"] = _iso_utc(_utc_now())
        _atomic_json(self.state_path, self.state)

    def record(
        self,
        *,
        method: str,
        path: str,
        raw_target: str,
        status: int,
        outcome: str,
        body: object = None,
        **details: object,
    ) -> None:
        with self.lock:
            event: dict[str, Any] = {
                "sequence": len(self.state["events"]) + 1,
                "at": _iso_utc(_utc_now()),
                "method": method,
                "path": path,
                "raw_target": raw_target,
                "status": status,
                "outcome": outcome,
            }
            if body is not None:
                event["body"] = body
            event.update(details)
            self.state["events"].append(event)
            self._persist()

    def silences(self) -> list[dict[str, Any]]:
        with self.lock:
            return json.loads(json.dumps(self.state["silences"]))

    def expire(self, silence_id: str) -> bool:
        with self.lock:
            for silence in self.state["silences"]:
                if silence.get("id") != silence_id:
                    continue
                if silence.get("status", {}).get("state") != "active":
                    return False
                silence["status"] = {"state": "expired"}
                silence["endsAt"] = _iso_utc(_utc_now())
                return True
        return False

    def create(self, body: dict[str, Any]) -> str:
        with self.lock:
            silence_id = "sil-" + uuid.uuid4().hex
            self.state["silences"].append(
                {
                    **json.loads(json.dumps(body)),
                    "id": silence_id,
                    "status": {"state": "active"},
                }
            )
            return silence_id

    def reload_status(self) -> tuple[int, str, str | None]:
        with self.lock:
            try:
                if (
                    not self.config_path.is_file()
                    or self.config_path.is_symlink()
                    or self.config_path.stat().st_size > 200_000
                ):
                    return 400, "config_unavailable", None
                config_sha256 = hashlib.sha256(
                    self.config_path.read_bytes()
                ).hexdigest()
            except OSError:
                return 400, "config_unavailable", None
            try:
                if hashlib.sha256(self.validator.read_bytes()).hexdigest() != self.validator_sha256:
                    return 500, "validator_tampered", config_sha256
                validated = subprocess.run(
                    [
                        sys.executable,
                        str(self.validator),
                        "check-config",
                        str(self.config_path),
                        "--utf8-strict",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                    env={
                        "HOME": "/tmp",
                        "LANG": "C.UTF-8",
                        "PATH": "/usr/local/bin:/usr/bin:/bin",
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                )
            except (OSError, subprocess.TimeoutExpired):
                return 500, "validator_unavailable", config_sha256
            if validated.returncode != 0:
                return 400, "config_invalid", config_sha256
            remaining = int(self.state["transient_reload_failures_remaining"])
            if remaining > 0:
                self.state["transient_reload_failures_remaining"] = remaining - 1
                return 503, "transient_failure", config_sha256
            self.state["active_config_sha256"] = config_sha256
            return 200, "reloaded", config_sha256

    def ready(self) -> bool:
        with self.lock:
            return isinstance(self.state.get("active_config_sha256"), str)


class RehearsalServer(ThreadingHTTPServer):
    store: RehearsalStore
    base_path: str


class RehearsalHandler(BaseHTTPRequestHandler):
    server: RehearsalServer

    def log_message(self, format_string: str, *args: object) -> None:
        return

    def _logical_target(self) -> tuple[str | None, str]:
        parsed = urlsplit(self.path)
        raw_path = parsed.path
        base = self.server.base_path
        if raw_path == base:
            logical = "/"
        elif raw_path.startswith(base + "/"):
            logical = raw_path[len(base) :]
        else:
            return None, self.path
        raw_target = logical
        if parsed.query:
            raw_target += "?" + parsed.query
        return logical, raw_target

    def _send(self, status: int, body: object = None) -> None:
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_response(status)
        if payload:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json_body(self) -> tuple[object, bool]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None, False
        if length < 0 or length > 65536:
            return None, False
        raw = self.rfile.read(length)
        if not raw:
            return None, True
        try:
            return json.loads(raw), True
        except json.JSONDecodeError:
            return raw.decode("utf-8", errors="replace"), False

    def _reject_method(self) -> None:
        path, raw_target = self._logical_target()
        self.server.store.record(
            method=self.command,
            path=path or "<outside-capability>",
            raw_target=raw_target,
            status=405,
            outcome="undeclared_method",
        )
        self._send(405, {"error": "undeclared method"})

    def do_GET(self) -> None:  # noqa: N802
        path, raw_target = self._logical_target()
        if path == "/healthz" and raw_target == path:
            self._send(200, {"ok": True})
            return
        if path == "/api/v2/silences":
            body = self.server.store.silences()
            self.server.store.record(
                method="GET",
                path=path,
                raw_target=raw_target,
                status=200,
                outcome="listed",
            )
            self._send(200, body)
            return
        if path == "/-/ready":
            ready = self.server.store.ready()
            status = 200 if ready else 503
            self.server.store.record(
                method="GET",
                path=path,
                raw_target=raw_target,
                status=status,
                outcome="ready" if ready else "not_ready",
            )
            self._send(status, None if ready else {"error": "reload not complete"})
            return
        self.server.store.record(
            method="GET",
            path=path or "<outside-capability>",
            raw_target=raw_target,
            status=404,
            outcome="undeclared_endpoint",
        )
        self._send(404, {"error": "undeclared endpoint"})

    def do_DELETE(self) -> None:  # noqa: N802
        path, raw_target = self._logical_target()
        prefix = "/api/v2/silence/"
        silence_id = (
            unquote(path[len(prefix) :]) if path and path.startswith(prefix) else ""
        )
        deleted = bool(silence_id) and self.server.store.expire(silence_id)
        status = 200 if deleted else 404
        self.server.store.record(
            method="DELETE",
            path=path or "<outside-capability>",
            raw_target=raw_target,
            status=status,
            outcome="expired" if deleted else "not_found",
        )
        self._send(status, None if deleted else {"error": "unknown silence"})

    def do_POST(self) -> None:  # noqa: N802
        path, raw_target = self._logical_target()
        body, valid_json = self._json_body()
        if path == "/api/v2/silences":
            if not valid_json or not isinstance(body, dict):
                self.server.store.record(
                    method="POST",
                    path=path,
                    raw_target=raw_target,
                    status=400,
                    outcome="invalid_payload",
                    body=body,
                )
                self._send(400, {"error": "silence payload must be an object"})
                return
            silence_id = self.server.store.create(body)
            self.server.store.record(
                method="POST",
                path=path,
                raw_target=raw_target,
                status=200,
                outcome="created",
                body=body,
            )
            self._send(200, {"silenceID": silence_id})
            return
        if path == "/-/reload":
            status, outcome, config_sha256 = self.server.store.reload_status()
            self.server.store.record(
                method="POST",
                path=path,
                raw_target=raw_target,
                status=status,
                outcome=outcome,
                body=body,
                config_sha256=config_sha256,
            )
            self._send(
                status,
                None
                if status == 200
                else {
                    "error": (
                        "transient rehearsal failure"
                        if status == 503
                        else (
                            "candidate configuration failed pinned validation"
                            if outcome == "config_invalid"
                            else "candidate configuration or validator is unavailable"
                        )
                    )
                },
            )
            return
        self.server.store.record(
            method="POST",
            path=path or "<outside-capability>",
            raw_target=raw_target,
            status=404,
            outcome="undeclared_endpoint",
            body=body,
        )
        self._send(404, {"error": "undeclared endpoint"})

    def do_HEAD(self) -> None:  # noqa: N802
        self._reject_method()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._reject_method()

    def do_PATCH(self) -> None:  # noqa: N802
        self._reject_method()

    def do_PUT(self) -> None:  # noqa: N802
        self._reject_method()

    def do_TRACE(self) -> None:  # noqa: N802
        self._reject_method()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--config-path", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--validator-sha256", required=True)
    parser.add_argument("--validator-version", required=True)
    args = parser.parse_args()
    if not args.base_path.startswith("/") or args.base_path.endswith("/"):
        raise SystemExit("base path must be an absolute path without a trailing slash")
    server = RehearsalServer((args.bind, args.port), RehearsalHandler)
    server.store = RehearsalStore(
        args.state_dir,
        args.instance_id,
        args.config_path,
        args.validator,
        args.validator_sha256,
        args.validator_version,
    )
    server.base_path = args.base_path
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
