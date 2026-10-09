"""Per-trial controller-managed task service lifecycle."""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from task_environment_runtime import (
    ResolvedTaskEnvironment,
    ServiceSpec,
    TaskEnvironmentError,
    TaskEnvironmentSpec,
)


_Docker = Callable[..., Any]


@dataclass(frozen=True)
class LocalServiceHandle:
    name: str
    container_name: str
    volume_name: str
    image_id: str
    public_base: str
    base_path: str
    private_state_path: Path


class TrialServiceRuntime:
    """Own one isolated Docker network and all sidecars for one evaluated trial."""

    def __init__(
        self,
        *,
        spec: TaskEnvironmentSpec,
        resolved: ResolvedTaskEnvironment,
        task_id: str,
        run_id: str,
        token: str,
        task_dir: Path,
        workspace: Path,
        artifact: Path,
        labels: list[str],
        docker_fn: _Docker,
    ) -> None:
        self.spec = spec
        self.resolved = resolved
        self.task_id = task_id
        self.run_id = run_id
        self.token = token
        self.task_dir = task_dir.resolve()
        self.workspace = workspace.resolve()
        self.artifact = artifact.resolve()
        self.labels = list(labels)
        self.docker = docker_fn
        self.network_name: str | None = None
        self._handles: dict[str, LocalServiceHandle] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return bool(self.spec.services)

    def create_network(self) -> None:
        if not self.enabled or self.network_name is not None:
            return
        safe_task = re.sub(r"[^a-z0-9]+", "-", self.task_id.casefold()).strip("-")
        self.network_name = f"hb-net-{safe_task[:20]}-{self.token[:8]}"
        self.docker(
            "network",
            "create",
            *self.labels,
            "--driver",
            "bridge",
            self.network_name,
        )
        self._events.append({"event": "network_created", "network": self.network_name})

    def _service(self, name: str) -> ServiceSpec:
        matches = [service for service in self.spec.services if service.name == name]
        if len(matches) != 1:
            raise TaskEnvironmentError(f"service is not declared exactly once: {name!r}")
        return matches[0]

    def launch_local(
        self,
        name: str,
        *,
        arguments: list[str],
        base_path: str,
    ) -> LocalServiceHandle:
        service = self._service(name)
        if service.script is None or service.image is not None:
            raise TaskEnvironmentError(f"service {name} is not a local task service")
        if name in self._handles:
            raise TaskEnvironmentError(f"service {name} has already been launched")
        if self.network_name is None:
            raise TaskEnvironmentError("trial service network was not created")
        if not isinstance(arguments, list) or not all(
            isinstance(value, str) and "\x00" not in value for value in arguments
        ):
            raise TaskEnvironmentError(f"service {name} arguments must be NUL-free strings")
        if (
            not base_path.startswith("/")
            or base_path.endswith("/")
            or ".." in base_path.split("/")
        ):
            raise TaskEnvironmentError(f"service {name} base_path is invalid")

        root = self.artifact / "services" / name
        root.mkdir(parents=True, exist_ok=False)
        snapshot_path = root / "state-snapshot.json"
        container_name = f"hb-svc-{self.task_id[:3]}-{name}-{self.token[:8]}"
        volume_name = f"hb-svc-state-{self.task_id[:3]}-{name}-{self.token[:8]}"
        environment_dir = self.task_dir / "environment"
        self.docker("volume", "create", *self.labels, volume_name)
        try:
            self.docker(
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "CHOWN",
                "--security-opt",
                "no-new-privileges:true",
                "--user",
                "0:0",
                "--mount",
                f"type=volume,src={volume_name},dst=/service-state",
                "--entrypoint",
                "sh",
                self.resolved.combined_image,
                "-c",
                "chmod 700 /service-state && chown 1000:1000 /service-state",
            )
        except Exception:
            self.docker("volume", "rm", "--force", volume_name, check=False)
            raise
        command = [
            "run",
            "--detach",
            "--no-healthcheck",
            "--name",
            container_name,
            *self.labels,
            "--network",
            self.network_name,
            "--network-alias",
            name,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            "128",
            "--memory",
            "1g",
            "--cpus",
            "1",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--user",
            "1000:1000",
            "--mount",
            f"type=bind,src={environment_dir},dst=/task-environment,readonly",
            "--mount",
            f"type=volume,src={volume_name},dst=/service-state",
            "--mount",
            f"type=bind,src={self.workspace},dst=/workspace,readonly",
            "--env",
            "HOME=/tmp",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONUNBUFFERED=1",
            "--entrypoint",
            "python3",
            self.resolved.combined_image,
            f"/task-environment/{service.script}",
            *arguments,
        ]
        handle = LocalServiceHandle(
            name=name,
            container_name=container_name,
            volume_name=volume_name,
            image_id=self.resolved.combined_image_id,
            public_base=f"http://{name}:{service.port}{base_path}",
            base_path=base_path,
            private_state_path=snapshot_path,
        )
        self._handles[name] = handle
        try:
            self.docker(*command)
            self._wait_healthy(service, handle)
            self.snapshot(name)
        except Exception:
            self._capture_logs(handle)
            self.docker("rm", "--force", container_name, check=False)
            self.docker("volume", "rm", "--force", volume_name, check=False)
            self._handles.pop(name, None)
            raise
        self._events.append(
            {
                "event": "service_healthy",
                "name": name,
                "container": container_name,
                "image_id": handle.image_id,
                "public_base": handle.public_base,
            }
        )
        return handle

    def _health_result(
        self,
        service: ServiceSpec,
        handle: LocalServiceHandle,
    ) -> subprocess.CompletedProcess[str]:
        health_url = (
            f"http://127.0.0.1:{service.port}"
            f"{handle.base_path}{service.health_path}"
        )
        probe = (
            "import urllib.request; "
            f"response=urllib.request.urlopen({health_url!r}, timeout=1); "
            "raise SystemExit(0 if response.status == 200 else 1)"
        )
        return self.docker(
            "exec",
            handle.container_name,
            "python3",
            "-c",
            probe,
            check=False,
        )

    def _wait_healthy(
        self,
        service: ServiceSpec,
        handle: LocalServiceHandle,
    ) -> None:
        deadline = time.monotonic() + service.health_timeout_sec
        last_detail = ""
        while time.monotonic() < deadline:
            inspect = self.docker(
                "inspect",
                "--format",
                "{{json .State}}",
                handle.container_name,
                check=False,
            )
            if inspect.returncode != 0:
                last_detail = inspect.stderr[-500:]
                break
            try:
                state = json.loads(inspect.stdout)
            except json.JSONDecodeError:
                state = {}
            if state.get("Running") is not True:
                last_detail = str(state)
                break
            result = self._health_result(service, handle)
            if result.returncode == 0:
                return
            last_detail = (result.stderr or result.stdout)[-500:]
            time.sleep(0.1)
        raise TaskEnvironmentError(
            f"service {service.name} did not become healthy: {last_detail}"
        )

    def check_healthy(self, name: str) -> None:
        service = self._service(name)
        handle = self._handles.get(name)
        if handle is None:
            raise TaskEnvironmentError(f"service {name} is not running")
        result = self._health_result(service, handle)
        if result.returncode != 0:
            raise TaskEnvironmentError(
                f"service {name} health check failed: {(result.stderr or result.stdout)[-500:]}"
            )

    def snapshot(self, name: str) -> Path:
        service = self._service(name)
        handle = self._handles.get(name)
        if handle is None:
            raise TaskEnvironmentError(f"service {name} is not running")
        script = (
            "from pathlib import Path; "
            f"print(Path('/service-state/{service.state_file}').read_text("
            "encoding='utf-8'), end='')"
        )
        completed = self.docker(
            "exec",
            handle.container_name,
            "python3",
            "-c",
            script,
            check=False,
        )
        if completed.returncode != 0:
            raise TaskEnvironmentError(
                f"service {name} state snapshot failed: "
                f"{(completed.stderr or completed.stdout)[-500:]}"
            )
        payload = completed.stdout
        if len(payload.encode("utf-8")) > 8_000_000:
            raise TaskEnvironmentError(f"service {name} state snapshot is oversized")
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TaskEnvironmentError(
                f"service {name} state snapshot is not valid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise TaskEnvironmentError(f"service {name} state snapshot is not an object")
        temporary = handle.private_state_path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(handle.private_state_path)
        self._events.append({"event": "state_snapshotted", "name": name})
        return handle.private_state_path


    def handle(self, name: str) -> LocalServiceHandle:
        try:
            return self._handles[name]
        except KeyError as exc:
            raise TaskEnvironmentError(f"service {name} is not running") from exc

    def _capture_logs(self, handle: LocalServiceHandle) -> None:
        completed = self.docker("logs", handle.container_name, check=False)
        log_path = self.artifact / "services" / handle.name / "service.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            (completed.stdout or "") + (completed.stderr or ""),
            encoding="utf-8",
        )

    def cleanup(self) -> None:
        errors: list[str] = []
        for handle in reversed(tuple(self._handles.values())):
            try:
                self.snapshot(handle.name)
            except Exception as exc:
                errors.append(f"{handle.name} final snapshot: {type(exc).__name__}: {exc}")
            try:
                self._capture_logs(handle)
            except Exception as exc:
                errors.append(f"{handle.name} log capture: {type(exc).__name__}: {exc}")
            removed = self.docker("rm", "--force", handle.container_name, check=False)
            if removed.returncode != 0:
                errors.append(f"{handle.name} container cleanup: {removed.stderr[-500:]}")
            removed_volume = self.docker(
                "volume", "rm", "--force", handle.volume_name, check=False
            )
            if removed_volume.returncode != 0:
                errors.append(
                    f"{handle.name} volume cleanup: {removed_volume.stderr[-500:]}"
                )
            self._events.append({"event": "service_removed", "name": handle.name})
        self._handles.clear()
        if self.network_name is not None:
            removed = self.docker("network", "rm", self.network_name, check=False)
            if removed.returncode != 0:
                errors.append(f"network cleanup: {removed.stderr[-500:]}")
            self._events.append(
                {"event": "network_removed", "network": self.network_name}
            )
            self.network_name = None
        if errors:
            raise TaskEnvironmentError("; ".join(errors))

    def report(self) -> dict[str, Any]:
        return {
            "declared": [service.name for service in self.spec.services],
            "events": list(self._events),
            "active_containers": [
                handle.container_name for handle in self._handles.values()
            ],
            "network": self.network_name,
        }
