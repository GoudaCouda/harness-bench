"""Trusted runtime adapter for the task-052 appointment service."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_HERE = Path(__file__).resolve().parent
_SERVICE = _HERE / "service.py"
_FIXTURE = _HERE / "slots.json"
_TRUSTED_SNAPSHOT = ".hb_trusted_appointment_state.json"
_CLOCK_EPOCH = "2026-08-10T16:00:00Z"


def _available_port(bind_host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((bind_host, 0))
        return int(probe.getsockname()[1])


def _stop_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _local_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _trusted_now(state: dict[str, Any]) -> str:
    epoch_text = state.get("_clock_epoch")
    anchor = state.get("_clock_anchor_monotonic")
    if not isinstance(epoch_text, str) or not isinstance(anchor, float):
        raise RuntimeError("trusted scenario clock is unavailable")
    epoch = datetime.fromisoformat(epoch_text.replace("Z", "+00:00"))
    if epoch.tzinfo is None:
        raise RuntimeError("trusted scenario clock epoch has no timezone")
    elapsed = max(0.0, time.monotonic() - anchor)
    return (
        (epoch.astimezone(timezone.utc) + timedelta(seconds=elapsed))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def prepare_runtime(context: dict[str, Any]) -> dict[str, Any]:
    """Start a capability-addressed service with state outside agent mounts."""
    workspace = Path(context["workspace"]).resolve()
    runtime = Path(context["sandbox"]).resolve()
    private_root = Path(tempfile.mkdtemp(prefix="hb052-appointment-private-"))
    private_root.chmod(0o700)
    if private_root.is_relative_to(workspace) or private_root.is_relative_to(runtime):
        shutil.rmtree(private_root, ignore_errors=True)
        raise RuntimeError("trusted appointment state overlaps an agent-visible mount")

    bind_host = str(context.get("service_bind_host") or "127.0.0.1")
    public_host = str(context.get("service_public_host") or bind_host)
    capability = secrets.token_urlsafe(18).replace("_", "").replace("-", "")
    base_path = f"/appointment/{capability}"
    instance_id = "hb052-" + secrets.token_hex(8)
    clock_anchor_monotonic = time.monotonic()
    start_sidecar = context.get("start_local_sidecar")
    snapshot_sidecar = context.get("snapshot_local_sidecar")
    healthcheck_sidecar = context.get("check_local_sidecar")
    if all(
        callable(callback)
        for callback in (start_sidecar, snapshot_sidecar, healthcheck_sidecar)
    ):
        handle = start_sidecar(
            "appointment",
            arguments=[
                "--fixture",
                "/task-environment/slots.json",
                "--state-dir",
                "/service-state",
                "--bind",
                "0.0.0.0",
                "--port",
                "8080",
                "--base-path",
                base_path,
                "--instance-id",
                instance_id,
                "--clock-epoch",
                _CLOCK_EPOCH,
                "--clock-anchor-monotonic",
                str(clock_anchor_monotonic),
            ],
            base_path=base_path,
        )
        state_path = snapshot_sidecar("appointment")
        return {
            "MOCK_SITE_BASE": handle.public_base,
            "_private_root": state_path.parent,
            "_private_state_path": state_path,
            "_instance_id": instance_id,
            "_clock_epoch": _CLOCK_EPOCH,
            "_clock_anchor_monotonic": clock_anchor_monotonic,
            "_sidecar_managed": True,
            "_sidecar_healthcheck": healthcheck_sidecar,
            "_sidecar_snapshot": snapshot_sidecar,
        }
    errors: list[str] = []
    opener = _local_opener()

    for attempt in range(1, 6):
        attempt_root = private_root / f"attempt-{attempt}"
        state_dir = attempt_root / "state"
        attempt_root.mkdir(mode=0o700)
        state_dir.mkdir(mode=0o700)
        server_log = attempt_root / "service.log"
        port = _available_port(bind_host)
        command = [
            sys.executable,
            str(_SERVICE),
            "--fixture",
            str(_FIXTURE),
            "--state-dir",
            str(state_dir),
            "--bind",
            bind_host,
            "--port",
            str(port),
            "--base-path",
            base_path,
            "--instance-id",
            instance_id,
            "--clock-epoch",
            _CLOCK_EPOCH,
            "--clock-anchor-monotonic",
            str(clock_anchor_monotonic),
        ]
        environment = {
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        with server_log.open("ab") as output:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                env=environment,
            )
        health_host = "127.0.0.1" if bind_host in {"", "0.0.0.0"} else bind_host
        health_url = f"http://{health_host}:{port}{base_path}/healthz"
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with opener.open(health_url, timeout=0.3) as response:
                    if response.status == 200:
                        state_path = state_dir / "appointment-service-state.json"
                        if state_path.is_file():
                            return {
                                "MOCK_SITE_BASE": (
                                    f"http://{public_host}:{port}{base_path}"
                                ),
                                "_local_site_base": (
                                    f"http://{health_host}:{port}{base_path}"
                                ),
                                "_server_process": process,
                                "_private_root": private_root,
                                "_private_state_path": state_path,
                                "_instance_id": instance_id,
                                "_clock_epoch": _CLOCK_EPOCH,
                                "_clock_anchor_monotonic": clock_anchor_monotonic,
                            }
            except OSError:
                time.sleep(0.05)
        returncode = process.poll()
        _stop_process(process)
        detail = server_log.read_text(encoding="utf-8", errors="replace")[-1000:]
        errors.append(f"attempt {attempt}: returncode={returncode}; {detail}")
        shutil.rmtree(attempt_root, ignore_errors=True)

    shutil.rmtree(private_root, ignore_errors=True)
    raise RuntimeError("appointment service failed to start: " + "; ".join(errors))


def quiesce_environment(
    context: dict[str, Any],
    state: dict[str, Any],
    round_index: int,
) -> None:
    """Wait until the atomic service-state snapshot is readable."""
    del context, round_index
    if state.get("_sidecar_managed") is True:
        healthcheck = state.get("_sidecar_healthcheck")
        snapshot = state.get("_sidecar_snapshot")
        if not callable(healthcheck) or not callable(snapshot):
            raise RuntimeError("trusted sidecar controls are unavailable")
        healthcheck("appointment")
        state["_private_state_path"] = snapshot("appointment")
        path = state["_private_state_path"]
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("instance_id") != state.get("_instance_id"):
            raise RuntimeError("trusted sidecar state identity is inconsistent")
        return
    path = state.get("_private_state_path")
    if not isinstance(path, Path):
        raise RuntimeError("trusted service state path is unavailable")
    local_site = state.get("_local_site_base")
    if not isinstance(local_site, str):
        raise RuntimeError("trusted local service endpoint is unavailable")
    try:
        with _local_opener().open(local_site + "/healthz", timeout=1) as response:
            if response.status != 200:
                raise RuntimeError("appointment service health check failed")
    except OSError as exc:
        raise RuntimeError("appointment service could not quiesce") from exc
    deadline = time.monotonic() + 3.0
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("instance_id") == state.get("_instance_id"):
                return
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.03)
    raise RuntimeError(f"trusted service state did not quiesce: {last_error}")


def _publish_trusted_snapshot(workspace: Path, state: dict[str, Any]) -> Path:
    source = state.get("_private_state_path")
    if not isinstance(source, Path) or not source.is_file() or source.is_symlink():
        raise RuntimeError("private appointment state is unavailable")
    private_root = state.get("_private_root")
    if not isinstance(private_root, Path) or not source.resolve().is_relative_to(
        private_root.resolve()
    ):
        raise RuntimeError("private appointment state escaped its trusted directory")
    value = json.loads(source.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("instance_id") != state.get(
        "_instance_id"
    ):
        raise RuntimeError("private appointment state failed identity validation")
    value["trusted_snapshot_at"] = _trusted_now(state)

    destination = workspace / _TRUSTED_SNAPSHOT
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(
            f"{_TRUSTED_SNAPSHOT} unexpectedly exists before trusted publish"
        )
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    payload_bytes = payload.encode("utf-8")
    with destination.open("xb") as handle:
        handle.write(payload_bytes)
    destination.chmod(0o444)
    state["_post_round_snapshot_manifest"] = {
        "kind": "file",
        "sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "size": len(payload_bytes),
    }
    return destination


def after_round(
    context: dict[str, Any],
    state: dict[str, Any],
    adapter_result: Any,
) -> dict[str, Any]:
    """Publish authoritative state only after the untrusted agent has stopped."""
    del adapter_result
    quiesce_environment(context, state, int(context.get("round_index", 0)))
    _publish_trusted_snapshot(Path(context["workspace"]), state)
    return {}


def post_round_environment_mutations(
    context: dict[str, Any],
    state: dict[str, Any],
    round_index: int,
) -> dict[str, dict[str, dict[str, object]]]:
    """Content-address the sole trusted workspace write made after the round."""
    del context, round_index
    manifest = state.get("_post_round_snapshot_manifest")
    if not isinstance(manifest, dict):
        raise RuntimeError("trusted appointment snapshot manifest is unavailable")
    return {
        "created": {_TRUSTED_SNAPSHOT: dict(manifest)},
        "modified": {},
        "deleted": {},
    }


def cleanup_runtime(context: dict[str, Any], state: dict[str, Any]) -> None:
    del context
    if state.get("_sidecar_managed") is True:
        return
    process = state.get("_server_process")
    if isinstance(process, subprocess.Popen):
        _stop_process(process)
    private_root = state.get("_private_root")
    if isinstance(private_root, Path):
        shutil.rmtree(private_root, ignore_errors=True)
