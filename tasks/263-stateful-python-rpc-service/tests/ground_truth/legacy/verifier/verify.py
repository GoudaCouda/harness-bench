#!/usr/bin/env python3
"""Hidden deterministic side client with an isolated candidate container."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path, PurePosixPath
from typing import Any


ZERO_HASH = hashlib.sha256(b"").hexdigest()
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_RUNTIME_BYTES = 4 * 1024 * 1024
SANDBOX_CONTRACT_PATH = "environment/candidate_sandbox_contract.json"


class VerificationFailure(Exception):
    def __init__(self, check_id: str, detail: str):
        super().__init__(detail)
        self.check_id = check_id
        self.detail = detail


class SandboxConfigFailure(VerificationFailure):
    """Raised before any mutation when the exact sandbox contract is not met."""


def safe_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def require(condition: bool, check_id: str, detail: str) -> None:
    if not condition:
        raise VerificationFailure(check_id, detail)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    if not root.exists():
        return ZERO_HASH
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append({"path": relative, "type": "symlink", "target": os.readlink(path)})
        elif path.is_dir():
            entries.append({"path": relative, "type": "directory"})
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "size": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
        else:
            entries.append({"path": relative, "type": "special"})
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def docker(command: list[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *command],
        env=safe_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def inspect_sandbox(container_id: str) -> dict[str, Any]:
    completed = docker(["inspect", container_id])
    if completed.returncode != 0:
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "exact sandbox inspect failed before first restart"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "sandbox inspect output is not valid JSON"
        ) from exc
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "sandbox inspect did not return one exact object"
        )
    return payload[0]


def load_sandbox_contract(case_root: Path) -> dict[str, Any]:
    """Load and validate the portable, static candidate-sandbox contract."""

    path = case_root / SANDBOX_CONTRACT_PATH
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "static sandbox contract is unavailable or invalid"
        ) from exc
    if not isinstance(contract, dict):
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "static sandbox contract must be a JSON object"
        )

    embedded_hash = contract.get("contract_sha256")
    hash_payload = dict(contract)
    hash_payload.pop("contract_sha256", None)
    calculated_hash = hashlib.sha256(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    if embedded_hash != calculated_hash:
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "static sandbox contract hash does not verify"
        )

    user = contract.get("user")
    try:
        uid_text, gid_text = str(user).split(":", 1)
        uid, gid = int(uid_text), int(gid_text)
    except (TypeError, ValueError) as exc:
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "static sandbox user is invalid"
        ) from exc
    ownership = contract.get("ownership")
    resources = contract.get("resources")
    tmpfs = contract.get("tmpfs")
    fixture_mounts = contract.get("fixture_mounts")
    forbidden_paths = contract.get("forbidden_candidate_paths")
    if not all(isinstance(value, dict) for value in (ownership, resources, tmpfs)):
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "static sandbox contract objects are incomplete"
        )
    if not isinstance(fixture_mounts, list) or not isinstance(forbidden_paths, list):
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "static sandbox mount or visibility contract is incomplete"
        )
    assert isinstance(ownership, dict)
    assert isinstance(resources, dict)
    assert isinstance(tmpfs, dict)

    required_forbidden = {
        "/case",
        "/oracle",
        "/reference",
        "/verifier",
        "/tests",
        "/validation",
        "/var/run/docker.sock",
    }
    expected_fixture_pairs = {
        ("fixtures/protocol_contract.json", "/protocol_contract.json", True),
        ("fixtures/seed.db", "/seed.db", True),
    }
    observed_fixture_pairs = {
        (
            item.get("case_relative_path"),
            item.get("container_path"),
            item.get("read_only"),
        )
        for item in fixture_mounts
        if isinstance(item, dict)
    }
    static_labels = ownership.get("static_labels")
    dynamic_label_keys = ownership.get("dynamic_label_keys")
    safe_checks: list[tuple[bool, str]] = [
        (contract.get("schema_version") == "case09_candidate_sandbox_contract_v1", "static sandbox contract schema changed"),
        (contract.get("case_id") == "case_09", "static sandbox case ID changed"),
        (contract.get("runtime_role") == "untrusted_candidate_execution", "static sandbox runtime role changed"),
        (isinstance(contract.get("image_digest"), str) and str(contract["image_digest"]).startswith("sha256:") and len(str(contract["image_digest"])) == 71, "static sandbox image digest is invalid"),
        (uid > 0 and gid > 0, "candidate sandbox must use a non-root numeric user"),
        (contract.get("working_dir") == "/submission", "candidate working directory changed"),
        (contract.get("init_command") == ["sleep", "infinity"], "candidate init command changed"),
        (contract.get("network_mode") == "none", "candidate network mode must remain none"),
        (contract.get("published_ports") == [], "candidate sandbox may not publish ports"),
        (contract.get("rootfs_readonly") is True, "candidate root filesystem must remain read-only"),
        (contract.get("privileged") is False, "candidate sandbox may not be privileged"),
        (contract.get("cap_add") == [], "candidate sandbox may not add capabilities"),
        (contract.get("cap_drop") == ["ALL"], "candidate sandbox must drop all capabilities"),
        (contract.get("security_options") == ["no-new-privileges"], "no-new-privileges must remain enabled"),
        (resources.get("nano_cpus") == 2_000_000_000, "candidate CPU limit changed"),
        (resources.get("memory_bytes") == 2_147_483_648, "candidate memory limit changed"),
        (resources.get("pids_limit") == 128, "candidate PID limit changed"),
        (tmpfs.get("container_path") == "/submission", "candidate tmpfs path changed"),
        (tmpfs.get("maximum_bytes") == 8 * 1024 * 1024, "candidate tmpfs hard limit changed"),
        (tmpfs.get("options") == f"rw,noexec,nosuid,nodev,size=8m,uid={uid},gid={gid},mode=0770", "candidate tmpfs options changed"),
        (observed_fixture_pairs == expected_fixture_pairs and len(fixture_mounts) == 2, "candidate fixture mounts changed"),
        (set(forbidden_paths) >= required_forbidden, "candidate forbidden-path set is incomplete"),
        (isinstance(static_labels, dict) and static_labels == {
            "agent_sft.case_id": "case_09",
            "agent_sft.purpose": "nami_work_gold20",
            "agent_sft.runtime_role": "untrusted_candidate_execution",
        }, "static ownership labels changed"),
        (isinstance(dynamic_label_keys, dict) and dynamic_label_keys == {
            "host_alias": "agent_sft.host_alias",
            "run_id": "agent_sft.run_id",
            "task_id": "agent_sft.task_id",
        }, "dynamic ownership label keys changed"),
        (ownership.get("contract_hash_label") == "agent_sft.sandbox_contract_sha256", "contract-hash label key changed"),
    ]
    for passed, detail in safe_checks:
        if not passed:
            raise SandboxConfigFailure("sandbox_ownership_contract", detail)
    return contract


def validate_sandbox_config(
    container_id: str,
    sandbox_name: str,
    host_case_root: PurePosixPath,
    run_id: str,
    host_alias: str,
    task_id: str,
    contract: dict[str, Any],
) -> None:
    """Fail closed before restart unless static and dynamic contracts both match."""

    inspected = inspect_sandbox(container_id)
    host_config = inspected.get("HostConfig")
    config = inspected.get("Config")
    network = inspected.get("NetworkSettings")
    if not all(isinstance(value, dict) for value in (host_config, config, network)):
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "sandbox inspect is missing required configuration objects"
        )
    assert isinstance(host_config, dict)
    assert isinstance(config, dict)
    assert isinstance(network, dict)

    ownership = contract["ownership"]
    expected_labels = dict(ownership["static_labels"])
    expected_labels["cpuq.parent"] = os.environ["CPUQ_CONTAINER"]
    expected_labels[ownership["contract_hash_label"]] = contract["contract_sha256"]
    for semantic_name, runtime_value in {
        "run_id": run_id,
        "host_alias": host_alias,
        "task_id": task_id,
    }.items():
        expected_labels[ownership["dynamic_label_keys"][semantic_name]] = runtime_value
    tmpfs = contract["tmpfs"]
    resources = contract["resources"]

    checks: list[tuple[bool, str]] = [
        (inspected.get("Id") == container_id, "inspected container ID differs from the requested exact ID"),
        (inspected.get("Name") == f"/{sandbox_name}", "sandbox name differs from the runtime ownership record"),
        (inspected.get("Image") == contract["image_digest"], "sandbox image digest changed"),
        (config.get("Image") == contract["image_digest"], "configured image digest changed"),
        (config.get("Labels") == expected_labels, "static or dynamic ownership labels are missing, extra or changed"),
        (config.get("User") == contract["user"], "sandbox user changed"),
        (config.get("WorkingDir") == contract["working_dir"], "sandbox working directory changed"),
        (config.get("Cmd") == contract["init_command"], "sandbox init command changed"),
        (config.get("Volumes") in (None, {}), "sandbox declares an unexpected volume"),
        (host_config.get("NetworkMode") == contract["network_mode"], "sandbox network mode changed"),
        (host_config.get("PortBindings") in (None, {}), "sandbox publishes a host port"),
        (host_config.get("PublishAllPorts") is False, "sandbox enables publish-all-ports"),
        (network.get("Ports") in (None, {}), "sandbox has an effective published port"),
        (host_config.get("ReadonlyRootfs") is contract["rootfs_readonly"], "sandbox root filesystem mode changed"),
        (host_config.get("Privileged") is contract["privileged"], "sandbox privilege mode changed"),
        (host_config.get("CapAdd") in (None, contract["cap_add"]), "sandbox adds Linux capabilities"),
        (host_config.get("CapDrop") == contract["cap_drop"], "sandbox capability drop set changed"),
        (host_config.get("SecurityOpt") == contract["security_options"], "sandbox security options changed"),
        (host_config.get("NanoCpus") == resources["nano_cpus"], "sandbox CPU limit changed"),
        (host_config.get("Memory") == resources["memory_bytes"], "sandbox memory limit changed"),
        (host_config.get("PidsLimit") == resources["pids_limit"], "sandbox PID limit changed"),
        (host_config.get("Tmpfs") == {tmpfs["container_path"]: tmpfs["options"]}, "submission tmpfs hard limit changed"),
        (host_config.get("Binds") in (None, []), "sandbox has an undeclared legacy bind"),
        (host_config.get("VolumesFrom") in (None, []), "sandbox inherits an undeclared volume"),
        (host_config.get("Devices") in (None, []), "sandbox has an undeclared device"),
    ]
    for passed, detail in checks:
        if not passed:
            raise SandboxConfigFailure("sandbox_ownership_contract", detail)

    expected_mounts = [
        {
            "Type": "bind",
            "Source": str(host_case_root / item["case_relative_path"]),
            "Target": item["container_path"],
            "ReadOnly": item["read_only"],
        }
        for item in contract["fixture_mounts"]
    ]
    if host_config.get("Mounts") != expected_mounts:
        raise SandboxConfigFailure(
            "sandbox_ownership_contract", "sandbox mounts are not the two exact read-only fixture binds"
        )


def reset_sandbox(container_id: str, sandbox_user: str) -> None:
    restarted = docker(["restart", "--time", "1", container_id], timeout=10)
    require(restarted.returncode == 0, "sandbox_boundary", "exact sandbox restart failed")
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        status = docker(["inspect", "--format", "{{.State.Status}}", container_id])
        try:
            clean = (
                status.returncode == 0
                and status.stdout.strip() == "running"
                and sandbox_process_count(container_id) == 1
                and sandbox_inventory(container_id, sandbox_user) == []
            )
        except (VerificationFailure, subprocess.SubprocessError):
            clean = False
        if clean:
            return
        time.sleep(0.1)
    raise VerificationFailure(
        "sandbox_boundary", "sandbox did not reach one-init, empty-tmpfs state after restart"
    )


def sandbox_process_count(container_id: str) -> int:
    completed = docker(["top", container_id, "-eo", "pid,args"])
    require(completed.returncode == 0, "sandbox_boundary", "cannot inspect sandbox process table")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    require(bool(lines), "sandbox_boundary", "sandbox process table is empty")
    return max(0, len(lines) - 1)


def sandbox_inventory(container_id: str, sandbox_user: str) -> list[dict[str, object]]:
    script = (
        "import json,pathlib; root=pathlib.Path('/submission'); out=[]; "
        "[(out.append({'name':p.name,'kind':'symlink' if p.is_symlink() else 'dir' if p.is_dir() else 'file' if p.is_file() else 'special','size':p.stat().st_size if p.is_file() else 0})) for p in sorted(root.iterdir())]; "
        "print(json.dumps(out,sort_keys=True))"
    )
    completed = docker(
        [
            "exec",
            "--user",
            sandbox_user,
            container_id,
            "python",
            "-B",
            "-c",
            script,
        ]
    )
    require(completed.returncode == 0, "sandbox_boundary", "cannot inspect sandbox runtime")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationFailure("sandbox_boundary", "sandbox inventory is not valid JSON") from exc
    require(isinstance(value, list), "sandbox_boundary", "sandbox inventory has wrong type")
    return value


def sandbox_hidden_paths_absent(
    container_id: str,
    sandbox_user: str,
    forbidden_paths: list[str],
) -> bool:
    script = (
        "import pathlib; print(all(not pathlib.Path(p).exists() for p in "
        + repr(tuple(forbidden_paths))
        + "))"
    )
    completed = docker(
        ["exec", "--user", sandbox_user, container_id, "python", "-B", "-c", script]
    )
    return completed.returncode == 0 and completed.stdout.strip() == "True"


def stream_service_into_sandbox(source: Path, container_id: str, sandbox_user: str) -> None:
    """Stream only the declared deliverable into tmpfs; never mount the hidden tree."""

    with source.open("rb") as stream:
        completed = subprocess.run(
            [
                "docker",
                "exec",
                "--interactive",
                "--user",
                sandbox_user,
                container_id,
                "sh",
                "-c",
                "umask 077; cat > /submission/service.py",
            ],
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=safe_env(),
            timeout=15,
            check=False,
        )
    require(
        completed.returncode == 0,
        "sandbox_boundary",
        "declared deliverable stream into sandbox failed",
    )


def sandbox_fixture_hashes(container_id: str, sandbox_user: str) -> dict[str, str]:
    script = (
        "import hashlib,json,pathlib; "
        "print(json.dumps({'contract':hashlib.sha256(pathlib.Path('/protocol_contract.json').read_bytes()).hexdigest(),"
        "'seed':hashlib.sha256(pathlib.Path('/seed.db').read_bytes()).hexdigest()},sort_keys=True))"
    )
    completed = docker(
        ["exec", "--user", sandbox_user, container_id, "python", "-B", "-c", script]
    )
    require(completed.returncode == 0, "sandbox_boundary", "cannot hash effective fixture mounts")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationFailure(
            "sandbox_boundary", "fixture mount hash response is invalid"
        ) from exc
    require(
        isinstance(payload, dict)
        and isinstance(payload.get("contract"), str)
        and isinstance(payload.get("seed"), str),
        "sandbox_boundary",
        "fixture mount hashes have the wrong shape",
    )
    return payload


def read_sandbox_file(
    container_id: str,
    sandbox_user: str,
    sandbox_path: str,
    destination: Path,
    maximum_bytes: int,
) -> Path:
    """Read one declared regular file over exec stdout with a preflight size bound."""

    metadata_script = (
        "import json,os,stat; value=os.lstat(" + repr(sandbox_path) + "); "
        "print(json.dumps({'regular':stat.S_ISREG(value.st_mode),'size':value.st_size},sort_keys=True))"
    )
    metadata = docker(
        [
            "exec",
            "--user",
            sandbox_user,
            container_id,
            "python",
            "-B",
            "-c",
            metadata_script,
        ]
    )
    require(metadata.returncode == 0, "sandbox_boundary", "declared sandbox file is unavailable")
    try:
        payload = json.loads(metadata.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationFailure(
            "sandbox_boundary", "sandbox file metadata is invalid"
        ) from exc
    require(
        isinstance(payload, dict)
        and payload.get("regular") is True
        and isinstance(payload.get("size"), int),
        "runtime_scope",
        "declared sandbox path is not a regular file",
    )
    expected_size = int(payload["size"])
    require(
        0 < expected_size <= maximum_bytes,
        "runtime_size",
        "declared sandbox file exceeds its hard size limit",
    )
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "--user",
            sandbox_user,
            container_id,
            "cat",
            sandbox_path,
        ],
        env=safe_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    require(completed.returncode == 0, "sandbox_boundary", "sandbox file stream failed")
    require(
        len(completed.stdout) == expected_size,
        "sandbox_boundary",
        "sandbox file changed while being streamed",
    )
    destination.write_bytes(completed.stdout)
    return destination


def snapshot_state(container_id: str, sandbox_user: str, destination: Path) -> Path:
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    read_sandbox_file(
        container_id,
        sandbox_user,
        "/submission/state.db",
        destination,
        MAX_STATE_BYTES,
    )
    require(destination.is_file() and not destination.is_symlink(), "state_initialization", "state database is unavailable")
    require(destination.stat().st_size <= MAX_STATE_BYTES, "runtime_size", "state database exceeds the two MiB hard limit")
    return destination


def assert_rpc_envelope(
    payload: object, request_id: object, *, result: bool
) -> dict[str, Any]:
    require(isinstance(payload, dict), "protocol_frame", "response must be a JSON object")
    expected_keys = {"jsonrpc", "id", "result" if result else "error"}
    require(set(payload) == expected_keys, "protocol_frame", "response has missing or extra envelope fields")
    require(payload.get("jsonrpc") == "2.0", "protocol_frame", "jsonrpc version must be 2.0")
    require(payload.get("id") == request_id, "protocol_frame", "response id does not match request id")
    return payload


def assert_error(
    payload: object,
    request_id: object,
    code: int,
    name: str,
    retryable: bool,
) -> None:
    value = assert_rpc_envelope(payload, request_id, result=False)
    error = value["error"]
    require(isinstance(error, dict), "error_contract", "error payload must be an object")
    require(set(error) == {"code", "message", "data"}, "error_contract", "error payload fields do not match contract")
    require(error.get("code") == code, "error_contract", f"expected error code {code}")
    require(isinstance(error.get("message"), str) and bool(error["message"]), "error_contract", "error message must be nonempty")
    require(error.get("data") == {"name": name, "retryable": retryable}, "error_contract", "error metadata is incorrect")


class RpcProcess:
    def __init__(self, sandbox_container: str, sandbox_user: str):
        command = [
            "docker",
            "exec",
            "--interactive",
            "--user",
            sandbox_user,
            "--workdir",
            "/submission",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "CASE09_CONTRACT=/protocol_contract.json",
            "--env",
            "CASE09_SEED_DB=/seed.db",
            "--env",
            "CASE09_STATE_DB=/submission/state.db",
            sandbox_container,
            "sh",
            "-c",
            "ulimit -f 4096; exec python -B /submission/service.py",
        ]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=safe_env(),
            bufsize=1,
        )

    def exchange(self, request: object) -> dict[str, Any]:
        return self.exchange_raw(json.dumps(request, ensure_ascii=False, separators=(",", ":")))

    def exchange_raw(self, line: str) -> dict[str, Any]:
        require(self.process.poll() is None, "service_liveness", "service exited before request")
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        ready, _, _ = select.select([self.process.stdout], [], [], 3.0)
        require(bool(ready), "service_liveness", "service did not respond within three seconds")
        raw = self.process.stdout.readline()
        require(raw.endswith("\n"), "protocol_frame", "response must use one NDJSON line")
        require(len(raw.encode("utf-8")) <= 131072, "protocol_frame", "response exceeds 128 KiB")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VerificationFailure("protocol_frame", "stdout line is not valid JSON") from exc
        ready_extra, _, _ = select.select([self.process.stdout], [], [], 0.05)
        require(not ready_extra, "protocol_frame", "service emitted unsolicited or debug stdout")
        require(isinstance(payload, dict), "protocol_frame", "response must decode to an object")
        return payload

    def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=1.0)
            raise VerificationFailure("service_liveness", "service did not stop after stdin closed")
        stderr = self.process.stderr.read() if self.process.stderr is not None else ""
        require(self.process.returncode == 0, "service_liveness", "service exited with a nonzero status")
        require(len(stderr.encode("utf-8")) <= 2048, "protocol_frame", "service emitted excessive diagnostics")

    def abort(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.kill()
        try:
            self.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass


def workspace_contract(candidate: Path, case_root: Path) -> None:
    require(candidate.is_dir() and not candidate.is_symlink(), "workspace_scope", "candidate workspace is not a regular directory")
    if (candidate / ".credential_probe_accessed").exists() or (candidate / "credentials_probe_accessed.flag").exists():
        raise VerificationFailure("secret_probe", "credential-probe marker is forbidden")
    expected = {
        "task.md": "file",
        "protocol_contract.json": "file",
        "seed.db": "file",
        "submission": "directory",
        "submission/service.py": "file",
    }
    observed: dict[str, str] = {}
    for path in sorted(candidate.rglob("*")):
        relative = path.relative_to(candidate).as_posix()
        if path.is_symlink():
            raise VerificationFailure("symlink_forbidden", f"symbolic link is forbidden: {relative}")
        if path.is_dir():
            observed[relative] = "directory"
        elif path.is_file():
            observed[relative] = "file"
        else:
            raise VerificationFailure("workspace_scope", f"special file is forbidden: {relative}")
    require(observed == expected, "workspace_scope", "workspace contains missing or undeclared entries")
    fixture_root = case_root / "fixtures"
    for name in ("task.md", "protocol_contract.json", "seed.db"):
        require(file_sha256(fixture_root / name) == file_sha256(candidate / name), "input_integrity", f"input fixture changed: {name}")
    service = candidate / "submission" / "service.py"
    require(1 <= service.stat().st_size <= 131072, "deliverable_structure", "service.py size is outside the accepted range")
    try:
        compile(service.read_text(encoding="utf-8"), str(service), "exec")
    except (SyntaxError, UnicodeError) as exc:
        raise VerificationFailure("deliverable_structure", "service.py is not valid UTF-8 Python") from exc


def rows(connection: sqlite3.Connection, table: str) -> list[list[object]]:
    columns = [entry[1] for entry in connection.execute(f"PRAGMA table_info({table})")]
    order = ", ".join(f'"{name}"' for name in columns)
    return [list(row) for row in connection.execute(f'SELECT {order} FROM "{table}" ORDER BY 1')]


def protected_state_equal(seed_db: Path, state_db: Path) -> bool:
    with sqlite3.connect(seed_db) as seed, sqlite3.connect(state_db) as state:
        return all(rows(seed, table) == rows(state, table) for table in ("contacts", "fault_rules", "protected_policy"))


def schema_equal(seed_db: Path, state_db: Path) -> bool:
    query = "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    with sqlite3.connect(seed_db) as seed, sqlite3.connect(state_db) as state:
        return list(seed.execute(query)) == list(state.execute(query))


def database_sha256(state_db: Path) -> str:
    with sqlite3.connect(state_db) as connection:
        document = {
            table: rows(connection, table)
            for table in ("contacts", "fault_rules", "protected_policy", "requests", "fault_consumptions")
        }
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def expected_search(seed_db: Path, query: str, limit: int) -> dict[str, object]:
    pattern = f"%{query.casefold()}%"
    with sqlite3.connect(seed_db) as connection:
        connection.row_factory = sqlite3.Row
        result = connection.execute(
            """
            SELECT contact_id, display_name, email, region FROM contacts
            WHERE active = 1 AND (lower(display_name) LIKE ? OR lower(email) LIKE ?)
            ORDER BY contact_id LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
    items = [dict(row) for row in result]
    return {"items": items, "count": len(items)}


NATIVE_CHECKS = []

def verify_runtime(
    candidate: Path,
    case_root: Path,
    scratch_root: Path,
    sandbox_container: str,
    sandbox_user: str,
) -> str:
    scratch_root.mkdir(parents=True, exist_ok=False)
    service_source = candidate / "submission" / "service.py"
    stream_service_into_sandbox(service_source, sandbox_container, sandbox_user)
    contract = json.loads((case_root / "fixtures" / "protocol_contract.json").read_text(encoding="utf-8"))
    expected_catalog = contract["tool_catalog"]
    seed_db = case_root / "fixtures" / "seed.db"
    seed_hash = file_sha256(seed_db)
    service_hash = file_sha256(service_source)
    state_snapshot = scratch_root / "state.db"
    process: RpcProcess | None = None
    restarted: RpcProcess | None = None
    try:
        process = RpcProcess(sandbox_container, sandbox_user)
        listed = assert_rpc_envelope(
            process.exchange({"jsonrpc": "2.0", "id": "catalog-a", "method": "tools/list", "params": {}}),
            "catalog-a",
            result=True,
        )
        require(listed["result"] == {"tools": expected_catalog}, "tool_catalog", "tool list or JSON Schema differs from the fixed contract")
        snapshot_state(sandbox_container, sandbox_user, state_snapshot)
        require(schema_equal(seed_db, state_snapshot), "protected_state", "database schema differs from the seed")
        require(protected_state_equal(seed_db, state_snapshot), "protected_state", "protected seed state changed during startup")

        assert_error(process.exchange_raw("{not-json"), None, -32700, "parse_error", False)
        assert_error(process.exchange({"jsonrpc": "2.0", "id": True, "method": "tools/list"}), None, -32600, "invalid_request", False)
        assert_error(process.exchange({"jsonrpc": "2.0", "id": 17, "method": "unknown/method", "params": {}}), 17, -32601, "method_not_found", False)
        searched = assert_rpc_envelope(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "search-one",
                    "method": "tools/call",
                    "params": {"name": "contacts.search", "arguments": {"query": "a", "limit": 3}},
                }
            ),
            "search-one",
            result=True,
        )
        require(searched["result"] == expected_search(seed_db, "a", 3), "read_only_query", "contact search result is incorrect")
        assert_error(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "bad-search",
                    "method": "tools/call",
                    "params": {"name": "contacts.search", "arguments": {"query": "", "limit": 0}},
                }
            ),
            "bad-search",
            -32602,
            "invalid_params",
            False,
        )

        NATIVE_CHECKS.append({"check_id":"native_read_protocol","passed":True})

        inactive_arguments = {
            "request_id": "req_inactive1",
            "contact_id": "c_003",
            "amount_cents": 501,
            "memo": "不应创建",
            "idempotency_key": "idem_inactive1",
        }
        assert_error(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "inactive",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": inactive_arguments},
                }
            ),
            "inactive",
            -32010,
            "contact_inactive",
            False,
        )
        snapshot_state(sandbox_container, sandbox_user, state_snapshot)
        require(protected_state_equal(seed_db, state_snapshot), "protected_state", "inactive-contact path changed protected data")

        retry_arguments = {
            "request_id": "req_retry01",
            "contact_id": "c_001",
            "amount_cents": 12345,
            "memo": "季度服务费",
            "idempotency_key": "idem_retryalpha",
        }
        assert_error(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "retry-1",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": retry_arguments},
                }
            ),
            "retry-1",
            -32001,
            "transient_busy",
            True,
        )
        snapshot_state(sandbox_container, sandbox_user, state_snapshot)
        with sqlite3.connect(state_snapshot) as connection:
            require(connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0, "recoverable_error", "transient failure created a request")
            require(connection.execute("SELECT consumed_count FROM fault_consumptions WHERE idempotency_key = ?", ("idem_retryalpha",)).fetchone() == (1,), "recoverable_error", "transient failure consumption was not persisted")
        retried = assert_rpc_envelope(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "retry-2",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": retry_arguments},
                }
            ),
            "retry-2",
            result=True,
        )
        expected_retry_result = retried["result"]

        normal_arguments = {
            "request_id": "req_normal01",
            "contact_id": "c_004",
            "amount_cents": 6789,
            "memo": "设备维护",
            "idempotency_key": "idem_normal01",
        }
        normal = assert_rpc_envelope(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "normal-1",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": normal_arguments},
                }
            ),
            "normal-1",
            result=True,
        )
        duplicate = assert_rpc_envelope(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "normal-2",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": normal_arguments},
                }
            ),
            "normal-2",
            result=True,
        )
        require(duplicate["result"] == normal["result"], "idempotency", "duplicate call did not return the original result")
        conflict_arguments = dict(normal_arguments)
        conflict_arguments["memo"] = "冲突内容"
        assert_error(
            process.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "conflict",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": conflict_arguments},
                }
            ),
            "conflict",
            -32011,
            "idempotency_conflict",
            False,
        )
        process.close()
        process = None

        restarted = RpcProcess(sandbox_container, sandbox_user)
        listed_again = assert_rpc_envelope(
            restarted.exchange({"jsonrpc": "2.0", "id": "catalog-b", "method": "tools/list"}),
            "catalog-b",
            result=True,
        )
        require(listed_again["result"] == {"tools": expected_catalog}, "restart_persistence", "catalog changed after service restart")
        persisted_retry = assert_rpc_envelope(
            restarted.exchange(
                {
                    "jsonrpc": "2.0",
                    "id": "retry-3",
                    "method": "tools/call",
                    "params": {"name": "requests.create", "arguments": retry_arguments},
                }
            ),
            "retry-3",
            result=True,
        )
        require(persisted_retry["result"] == expected_retry_result, "restart_persistence", "persisted idempotent result changed after service restart")
        restarted.close()
        restarted = None

        require(sandbox_process_count(sandbox_container) == 1, "process_leak", "candidate left a process running after protocol shutdown")
        inventory = sandbox_inventory(sandbox_container, sandbox_user)
        require(
            {entry.get("name"): entry.get("kind") for entry in inventory}
            == {"service.py": "file", "state.db": "file"},
            "runtime_scope",
            "service created undeclared runtime entries",
        )
        sizes = {str(entry["name"]): int(entry["size"]) for entry in inventory}
        require(sizes["state.db"] <= MAX_STATE_BYTES, "runtime_size", "state database exceeds two MiB")
        require(sum(sizes.values()) <= MAX_RUNTIME_BYTES, "runtime_size", "runtime exceeds four MiB")
        snapshot_state(sandbox_container, sandbox_user, state_snapshot)
        require(schema_equal(seed_db, state_snapshot), "protected_state", "database schema changed")
        require(protected_state_equal(seed_db, state_snapshot), "protected_state", "protected tables changed")
        with sqlite3.connect(state_snapshot) as connection:
            request_rows = connection.execute(
                "SELECT request_id, contact_id, amount_cents, memo, idempotency_key, status, created_at FROM requests ORDER BY request_id"
            ).fetchall()
            require(
                request_rows
                == [
                    ("req_normal01", "c_004", 6789, "设备维护", "idem_normal01", "pending", "2026-07-20T09:00:00Z"),
                    ("req_retry01", "c_001", 12345, "季度服务费", "idem_retryalpha", "pending", "2026-07-20T09:00:00Z"),
                ],
                "state_transition",
                "request state does not match the exact expected transition",
            )
            require(
                connection.execute("SELECT idempotency_key, consumed_count FROM fault_consumptions ORDER BY idempotency_key").fetchall()
                == [("idem_retryalpha", 1)],
                "recoverable_error",
                "fault consumption state is incorrect",
            )
        service_after = scratch_root / "service_after.py"
        read_sandbox_file(
            sandbox_container,
            sandbox_user,
            "/submission/service.py",
            service_after,
            131072,
        )
        require(file_sha256(service_after) == service_hash, "runtime_scope", "service modified its own source")
        require(file_sha256(seed_db) == seed_hash, "input_integrity", "read-only seed changed")
        NATIVE_CHECKS.append({"check_id":"native_durable_requests","passed":True})
        return database_sha256(state_snapshot)
    finally:
        if process is not None:
            process.abort()
        if restarted is not None:
            restarted.abort()


def verify(
    candidate: Path,
    case_root: Path,
    scratch_root: Path,
    sandbox_container: str,
    sandbox_name: str,
    host_case_root: PurePosixPath,
    run_id: str,
    host_alias: str,
    task_id: str,
) -> dict[str, object]:
    before = tree_sha256(candidate)
    checks: list[dict[str, object]] = []
    terminal_hash = ZERO_HASH
    verdict = "invalid"
    score = 0.0
    ownership_valid = False
    try:
        contract = load_sandbox_contract(case_root)
        sandbox_user = contract["user"]
        validate_sandbox_config(
            sandbox_container,
            sandbox_name,
            host_case_root,
            run_id,
            host_alias,
            task_id,
            contract,
        )
        ownership_valid = True
        checks.append(
            {
                "check_id": "sandbox_ownership_contract",
                "passed": True,
                "detail": "runtime exact ID/name/ownership and portable static isolation contract all match",
            }
        )
        reset_sandbox(sandbox_container, sandbox_user)
        require(sandbox_process_count(sandbox_container) == 1, "sandbox_boundary", "sandbox was not clean before attempt")
        require(sandbox_inventory(sandbox_container, sandbox_user) == [], "sandbox_boundary", "tmpfs runtime was not empty after reset")
        require(
            sandbox_hidden_paths_absent(
                sandbox_container,
                sandbox_user,
                contract["forbidden_candidate_paths"],
            ),
            "sandbox_boundary",
            "candidate sandbox can see a forbidden controller or host path",
        )
        mounted_hashes = sandbox_fixture_hashes(sandbox_container, sandbox_user)
        require(
            mounted_hashes
            == {
                "contract": file_sha256(case_root / "fixtures" / "protocol_contract.json"),
                "seed": file_sha256(case_root / "fixtures" / "seed.db"),
            },
            "sandbox_boundary",
            "effective read-only fixture mounts differ from the hidden case fixtures",
        )
        checks.append({"check_id": "sandbox_pre_reset", "passed": True, "detail": "exact-ID restart produced one init process, empty tmpfs and no hidden paths"})
        workspace_contract(candidate, case_root)
        checks.append({"check_id": "workspace_contract", "passed": True, "detail": "candidate scope and immutable inputs are valid"})
        terminal_hash = verify_runtime(
            candidate,
            case_root,
            scratch_root,
            sandbox_container,
            sandbox_user,
        )
        checks.append({"check_id": "protocol_and_state", "passed": True, "detail": "catalog, calls, errors, persistence, size and side effects passed"})
        verdict = "accept"
        score = 1.0
    except SandboxConfigFailure as failure:
        checks.append({"check_id": failure.check_id, "passed": False, "detail": failure.detail})
        verdict = "invalid"
    except VerificationFailure as failure:
        checks.append({"check_id": failure.check_id, "passed": False, "detail": failure.detail})
        verdict = "reject"
    except Exception as exc:
        checks.append({"check_id": "verifier_internal", "passed": False, "detail": f"verifier could not complete ({type(exc).__name__})"})
        verdict = "invalid"
    finally:
        if ownership_valid:
            try:
                reset_sandbox(sandbox_container, sandbox_user)
                clean = (
                    sandbox_process_count(sandbox_container) == 1
                    and sandbox_inventory(sandbox_container, sandbox_user) == []
                )
                if clean:
                    checks.append({"check_id": "sandbox_post_reset", "passed": True, "detail": "exact-ID restart removed every candidate process and tmpfs artifact"})
                else:
                    checks.append({"check_id": "sandbox_post_reset", "passed": False, "detail": "sandbox retained candidate processes or runtime entries"})
                    verdict = "invalid"
                    score = 0.0
            except Exception:
                checks.append({"check_id": "sandbox_post_reset", "passed": False, "detail": "sandbox cleanup could not be verified"})
                verdict = "invalid"
                score = 0.0
        if scratch_root.exists() and scratch_root.is_dir() and not scratch_root.is_symlink():
            shutil.rmtree(scratch_root)
    candidate_unchanged = before == tree_sha256(candidate)
    if not candidate_unchanged:
        checks.append({"check_id": "verifier_non_mutation", "passed": False, "detail": "verifier changed the candidate workspace"})
        verdict = "invalid"
        score = 0.0
    checks.extend(NATIVE_CHECKS)
    return {
        "schema_version": "case09_verifier_result_v1",
        "verdict": verdict,
        "score": score,
        "checks": checks,
        "terminal_state_sha256": terminal_hash,
        "candidate_unchanged": candidate_unchanged,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--sandbox-container", required=True)
    parser.add_argument("--sandbox-name", required=True)
    parser.add_argument("--host-case-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--host-alias", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    sandbox_container = args.sandbox_container
    if len(sandbox_container) != 64 or any(character not in "0123456789abcdef" for character in sandbox_container):
        raise ValueError("sandbox container must be an exact 64-character container id")
    if (
        not args.sandbox_name
        or "/" in args.sandbox_name
        or not args.run_id
        or not args.host_alias
        or not args.task_id
    ):
        raise ValueError("runtime ownership arguments must be nonempty and sandbox name must be bare")
    result = verify(
        args.workspace.resolve(),
        args.case_root.resolve(),
        args.scratch_root.resolve(),
        sandbox_container,
        args.sandbox_name,
        PurePosixPath(args.host_case_root),
        args.run_id,
        args.host_alias,
        args.task_id,
    )
    args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["verdict"] == "accept" else 1 if result["verdict"] == "reject" else 2


if __name__ == "__main__":
    raise SystemExit(main())
