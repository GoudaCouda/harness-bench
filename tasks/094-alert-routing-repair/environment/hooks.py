"""Trusted runtime lifecycle for the task-094 Alertmanager rehearsal."""

from __future__ import annotations

import json
import hashlib
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any


_HERE = Path(__file__).resolve().parent
_SERVICE = _HERE / "service.py"
_VALIDATOR_SOURCE = _HERE / "alertmanager_validator.py"
_VALIDATOR_MANIFEST = _HERE / "alertmanager_validator.sha256"
_VALIDATOR_VERSION = "hb-amconfig-validator 0.32.1-profile.1"
_TRUSTED_SNAPSHOT = ".hb_trusted_alertmanager_state.json"


def _verified_validator_source() -> tuple[Path, str]:
    """Resolve the protected validator only after checking its package digest."""
    try:
        if (
            not _VALIDATOR_SOURCE.is_file()
            or _VALIDATOR_SOURCE.is_symlink()
            or not _VALIDATOR_MANIFEST.is_file()
            or _VALIDATOR_MANIFEST.is_symlink()
        ):
            raise RuntimeError("trusted validator package is not regular protected data")
        fields = _VALIDATOR_MANIFEST.read_text(encoding="ascii").strip().split()
        if len(fields) != 2 or fields[1] != _VALIDATOR_SOURCE.name:
            raise RuntimeError("trusted validator manifest is malformed")
        expected = fields[0]
        payload = _VALIDATOR_SOURCE.read_bytes()
    except OSError as exc:
        raise RuntimeError("trusted validator package is unavailable") from exc
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError("trusted validator source failed its content-address check")
    return _VALIDATOR_SOURCE, actual


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


def prepare_runtime(context: dict[str, Any]) -> dict[str, Any]:
    """Start private state and expose only a capability-scoped API address."""
    workspace = Path(context["workspace"]).resolve()
    runtime = Path(context["sandbox"]).resolve()
    private_root = Path(tempfile.mkdtemp(prefix="hb094-alertmanager-private-"))
    private_root.chmod(0o700)
    if private_root.is_relative_to(workspace) or private_root.is_relative_to(runtime):
        shutil.rmtree(private_root, ignore_errors=True)
        raise RuntimeError("trusted Alertmanager state overlaps an agent-visible mount")

    bind_host = str(context.get("service_bind_host") or "127.0.0.1")
    public_host = str(context.get("service_public_host") or bind_host)
    capability = secrets.token_urlsafe(24).replace("_", "").replace("-", "")
    base_path = f"/alertmanager/{capability}"
    instance_id = "hb094-" + secrets.token_hex(12)
    opener = _local_opener()
    errors: list[str] = []
    validator_source, validator_sha256 = _verified_validator_source()
    try:
        validator_probe = subprocess.run(
            [sys.executable, str(validator_source), "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={
                "HOME": "/tmp",
                "LANG": "C.UTF-8",
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("trusted validator could not be executed") from exc
    if validator_probe.returncode != 0 or validator_probe.stdout.strip() != _VALIDATOR_VERSION:
        raise RuntimeError("trusted validator reports the wrong fixed version")
    runtime_validator = runtime / "hb-amconfig"
    runtime_validator.write_bytes(validator_source.read_bytes())
    runtime_validator.chmod(0o555)
    start_sidecar = context.get("start_local_sidecar")
    snapshot_sidecar = context.get("snapshot_local_sidecar")
    healthcheck_sidecar = context.get("check_local_sidecar")
    if all(
        callable(callback)
        for callback in (start_sidecar, snapshot_sidecar, healthcheck_sidecar)
    ):
        shutil.rmtree(private_root, ignore_errors=True)
        handle = start_sidecar(
            "alertmanager",
            arguments=[
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
                "--config-path",
                "/workspace/repo/alertmanager.yml",
                "--validator",
                "/task-environment/alertmanager_validator.py",
                "--validator-sha256",
                validator_sha256,
                "--validator-version",
                _VALIDATOR_VERSION,
            ],
            base_path=base_path,
        )
        env_path = runtime / "alertmanager.env"
        env_path.write_text(
            "export ALERTMANAGER_URL=" + repr(handle.public_base) + "\n"
            "export ALERTMANAGER_VALIDATOR=/runtime/hb-amconfig\n",
            encoding="utf-8",
        )
        env_path.chmod(0o444)
        state_path = snapshot_sidecar("alertmanager")
        return {
            "ALERTMANAGER_URL": handle.public_base,
            "ALERTMANAGER_ENV": "/runtime/alertmanager.env",
            "_private_root": state_path.parent,
            "_private_state_path": state_path,
            "_instance_id": instance_id,
            "_validator_sha256": validator_sha256,
            "_validator_version": _VALIDATOR_VERSION,
            "_sidecar_managed": True,
            "_sidecar_healthcheck": healthcheck_sidecar,
            "_sidecar_snapshot": snapshot_sidecar,
        }

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
            "--config-path",
            str(workspace / "repo" / "alertmanager.yml"),
            "--validator",
            str(validator_source),
            "--validator-sha256",
            validator_sha256,
            "--validator-version",
            _VALIDATOR_VERSION,
        ]
        with server_log.open("ab") as output:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                env={
                    "HOME": "/tmp",
                    "LANG": "C.UTF-8",
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUNBUFFERED": "1",
                },
            )
        health_host = "127.0.0.1" if bind_host in {"", "0.0.0.0"} else bind_host
        local_base = f"http://{health_host}:{port}{base_path}"
        # Importing the protected YAML validator from a cold shared filesystem
        # can take several seconds on the host-native runner.
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                with opener.open(local_base + "/healthz", timeout=0.3) as response:
                    state_path = state_dir / "alertmanager-rehearsal-state.json"
                    if response.status == 200 and state_path.is_file():
                        public_base = f"http://{public_host}:{port}{base_path}"
                        env_path = runtime / "alertmanager.env"
                        env_path.write_text(
                            "export ALERTMANAGER_URL=" + repr(public_base) + "\n"
                            "export ALERTMANAGER_VALIDATOR=/runtime/hb-amconfig\n",
                            encoding="utf-8",
                        )
                        env_path.chmod(0o444)
                        return {
                            "ALERTMANAGER_URL": public_base,
                            "ALERTMANAGER_ENV": "/runtime/alertmanager.env",
                            "_local_alertmanager_url": local_base,
                            "_server_process": process,
                            "_private_root": private_root,
                            "_private_state_path": state_path,
                            "_instance_id": instance_id,
                            "_validator_sha256": validator_sha256,
                            "_validator_version": _VALIDATOR_VERSION,
                        }
            except OSError:
                time.sleep(0.05)
        returncode = process.poll()
        _stop_process(process)
        detail = server_log.read_text(encoding="utf-8", errors="replace")[-1000:]
        errors.append(f"attempt {attempt}: returncode={returncode}; {detail}")
        shutil.rmtree(attempt_root, ignore_errors=True)

    shutil.rmtree(private_root, ignore_errors=True)
    raise RuntimeError("Alertmanager rehearsal failed to start: " + "; ".join(errors))


def quiesce_environment(
    context: dict[str, Any], state: dict[str, Any], round_index: int
) -> None:
    """Wait until the service's atomic private ledger can be read."""
    del context, round_index
    if state.get("_sidecar_managed") is True:
        healthcheck = state.get("_sidecar_healthcheck")
        snapshot = state.get("_sidecar_snapshot")
        if not callable(healthcheck) or not callable(snapshot):
            raise RuntimeError("trusted sidecar controls are unavailable")
        healthcheck("alertmanager")
        state["_private_state_path"] = snapshot("alertmanager")
        path = state["_private_state_path"]
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("instance_id") != state.get("_instance_id"):
            raise RuntimeError("trusted sidecar state identity is inconsistent")
        return
    path = state.get("_private_state_path")
    if not isinstance(path, Path):
        raise RuntimeError("trusted Alertmanager state path is unavailable")
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
    raise RuntimeError(f"trusted Alertmanager state did not quiesce: {last_error}")


def _publish_trusted_snapshot(workspace: Path, state: dict[str, Any]) -> Path:
    source = state.get("_private_state_path")
    private_root = state.get("_private_root")
    if not isinstance(source, Path) or not source.is_file() or source.is_symlink():
        raise RuntimeError("private Alertmanager state is unavailable")
    if not isinstance(private_root, Path) or not source.resolve().is_relative_to(
        private_root.resolve()
    ):
        raise RuntimeError("private Alertmanager state escaped its trusted directory")
    value = json.loads(source.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("instance_id") != state.get(
        "_instance_id"
    ):
        raise RuntimeError("private Alertmanager state failed identity validation")

    destination = workspace / _TRUSTED_SNAPSHOT
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"{_TRUSTED_SNAPSHOT} unexpectedly exists before publish")
    destination.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    destination.chmod(0o444)
    return destination


def after_round(
    context: dict[str, Any], state: dict[str, Any], adapter_result: Any
) -> dict[str, Any]:
    """Freeze and publish authoritative state after the untrusted round ends."""
    del adapter_result
    quiesce_environment(context, state, int(context.get("round_index", 0)))
    process = state.get("_server_process")
    if isinstance(process, subprocess.Popen):
        _stop_process(process)
    snapshot = _publish_trusted_snapshot(Path(context["workspace"]), state)
    payload = snapshot.read_bytes()
    state["_trusted_snapshot_manifest"] = {
        "kind": "file",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    return {}


def post_round_environment_mutations(
    context: dict[str, Any], state: dict[str, Any], round_index: int
) -> dict[str, dict[str, dict[str, object]]]:
    """Content-address the sole controller-owned post-round workspace write."""
    del round_index
    snapshot = Path(context["workspace"]) / _TRUSTED_SNAPSHOT
    expected = state.get("_trusted_snapshot_manifest")
    if (
        not isinstance(expected, dict)
        or not snapshot.is_file()
        or snapshot.is_symlink()
    ):
        raise RuntimeError("trusted Alertmanager snapshot provenance is unavailable")
    payload = snapshot.read_bytes()
    actual = {
        "kind": "file",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }
    if actual != expected:
        raise RuntimeError("trusted Alertmanager snapshot changed after publish")
    return {
        "created": {_TRUSTED_SNAPSHOT: actual},
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
