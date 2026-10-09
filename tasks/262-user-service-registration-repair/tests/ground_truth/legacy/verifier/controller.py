from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import sqlite3
import stat
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


RESULT_PREFIX = "CASE08_RESULT "
MAX_EXEC_OUTPUT_BYTES = 262_144
MAX_WORKSPACE_FILE_BYTES = 67_108_864
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SENSITIVE_ENV_MARKERS = (
    "API_KEY",
    "ANTHROPIC",
    "AWS_",
    "AZURE_",
    "GITHUB_TOKEN",
    "OPENAI",
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "WANDB",
)


@dataclass(frozen=True)
class Check:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class RunnerCall:
    call_id: str
    status: str
    exit_code: int | None
    output_bytes: int
    output_sha256: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hidden controller for isolated case_08 verification"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--host-alias", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--container-id", required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--submitted-workspace", required=True, type=Path)
    parser.add_argument("--sandbox-contract", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--runtime-workspace", required=True, type=Path)
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--initial-state-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def workspace_sha256(root: Path) -> str:
    base = root.resolve(strict=True)
    digest = hashlib.sha256()
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        if path.is_symlink():
            raise ValueError("workspace cannot contain symbolic links")
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        if path.is_dir():
            digest.update(b"D")
        elif path.is_file():
            digest.update(b"F")
            content = path.read_bytes()
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        else:
            raise ValueError("workspace contains unsupported filesystem entry")
    return digest.hexdigest()


def file_map(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            values[relative.as_posix()] = "SYMLINK"
        elif path.is_dir():
            values[relative.as_posix()] = "DIRECTORY"
        elif path.is_file():
            values[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            values[relative.as_posix()] = "UNSUPPORTED"
    return values


def read_contract(path: Path) -> tuple[dict[str, Any], str]:
    envelope = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(envelope, dict) or not isinstance(envelope.get("contract"), dict):
        raise ValueError("sandbox contract envelope is invalid")
    contract = envelope["contract"]
    digest = canonical_hash(contract)
    if envelope.get("contract_sha256") != digest:
        raise ValueError("sandbox contract digest mismatch")
    return contract, digest


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def require_no_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"managed path contains symbolic link: {current}")


def managed_runtime_paths(runtime_root: Path, workspace: Path) -> tuple[Path, Path]:
    root = lexical_absolute(runtime_root)
    candidate = lexical_absolute(workspace)
    if not root.is_dir() or not candidate.is_dir():
        raise ValueError("managed runtime paths must already be directories")
    require_no_symlink_components(root)
    require_no_symlink_components(candidate)
    if candidate.parent != root:
        raise ValueError("runtime workspace is outside exact managed runtime root")
    if root.resolve(strict=True) != root or candidate.resolve(strict=True) != candidate:
        raise ValueError("managed runtime paths must be canonical")
    return root, candidate


def docker(args: list[str], *, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def require_docker(args: list[str], *, timeout: float = 30) -> str:
    completed = docker(args, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(f"docker_{args[0]}_failed")
    return completed.stdout


def expected_labels(
    args: argparse.Namespace,
    contract: dict[str, Any],
    contract_sha256: str,
) -> dict[str, str]:
    dynamic_values = {
        "run_id": args.run_id,
        "task_id": args.task_id,
        "host_alias": args.host_alias,
        "attempt_id": args.attempt_id,
    }
    if not all(SAFE_ID.fullmatch(str(value)) for value in dynamic_values.values()):
        raise ValueError("dynamic ownership label contains unsafe characters")
    return {
        "agent_sft.run_id": args.run_id,
        "agent_sft.task_id": args.task_id,
        "agent_sft.case_id": str(contract["case_id"]),
        "agent_sft.variant": str(contract["variant"]),
        "agent_sft.host_alias": args.host_alias,
        "agent_sft.attempt_id": args.attempt_id,
        "agent_sft.role": str(contract["role"]),
        "agent_sft.sandbox_contract_sha256": contract_sha256,
    }


def inspect_contract(args: argparse.Namespace) -> dict[str, Any]:
    contract_spec, contract_sha256 = read_contract(args.sandbox_contract)
    runtime_root, runtime_workspace = managed_runtime_paths(
        args.runtime_root,
        args.runtime_workspace,
    )
    raw = require_docker(["inspect", args.container_id])
    values = json.loads(raw)
    if not isinstance(values, list) or len(values) != 1:
        raise RuntimeError("inspect_cardinality_mismatch")
    value = values[0]
    config = value.get("Config", {})
    host = value.get("HostConfig", {})
    mounts = value.get("Mounts", [])
    state = value.get("State", {})
    labels = config.get("Labels") or {}
    env = config.get("Env") or []
    environment = {
        item.split("=", 1)[0]: item.split("=", 1)[1] if "=" in item else ""
        for item in env
    }
    sensitive_env_names = sorted(
        name
        for name, content in environment.items()
        if content
        and any(marker in name.upper() for marker in SENSITIVE_ENV_MARKERS)
    )
    ulimits = {
        item.get("Name"): (item.get("Soft"), item.get("Hard"))
        for item in host.get("Ulimits") or []
    }
    tmpfs = host.get("Tmpfs") or {}
    scratch_spec = contract_spec["tmpfs"][0]
    expected_tmpfs_tokens = {
        *(str(item) for item in scratch_spec["options"]),
        f"size={scratch_spec['size_bytes']}",
    }
    actual_tmpfs_tokens = set(str(tmpfs.get("/scratch", "")).split(","))
    expected_mount_source = runtime_workspace.as_posix()
    mount_contract = (
        len(mounts) == 1
        and mounts[0].get("Type") == "bind"
        and mounts[0].get("Source") == expected_mount_source
        and mounts[0].get("Destination") == "/workspace"
        and mounts[0].get("RW") is True
        and mounts[0].get("Propagation") == "rprivate"
    )
    security_opt = set(host.get("SecurityOpt") or [])
    cap_drop = {str(item).upper() for item in host.get("CapDrop") or []}
    port_bindings = host.get("PortBindings") or {}
    exposed_ports = config.get("ExposedPorts") or {}
    restart_policy = host.get("RestartPolicy") or {}
    contract = {
        "exact_id": value.get("Id") == args.container_id,
        "exact_name": value.get("Name") == f"/{args.container_name}",
        "labels": all(
            labels.get(key) == content
            for key, content in expected_labels(
                args,
                contract_spec,
                contract_sha256,
            ).items()
        ),
        "role": labels.get("agent_sft.role") == contract_spec["role"],
        "contract_hash_label": labels.get(
            "agent_sft.sandbox_contract_sha256"
        )
        == contract_sha256,
        "image": value.get("Image") == args.image_id,
        "network_none": host.get("NetworkMode") == contract_spec["network_mode"],
        "no_ports": not port_bindings and not exposed_ports,
        "nonroot_user": config.get("User") == contract_spec["user"],
        "readonly_rootfs": host.get("ReadonlyRootfs")
        is contract_spec["readonly_rootfs"],
        "cap_drop_all": set(contract_spec["cap_drop"]).issubset(cap_drop),
        "no_new_privileges": any(
            item.startswith("no-new-privileges") for item in security_opt
        ),
        "not_privileged": host.get("Privileged") is False,
        "cpu_limit": host.get("NanoCpus")
        == int(float(contract_spec["cpu_cores"]) * 1_000_000_000),
        "memory_limit": host.get("Memory") == contract_spec["memory_bytes"],
        "memory_swap_limit": host.get("MemorySwap")
        == contract_spec["memory_swap_bytes"],
        "pid_limit": host.get("PidsLimit") == contract_spec["pids_limit"],
        "file_size_limit": ulimits.get("fsize")
        == (
            contract_spec["file_size_limit_bytes"],
            contract_spec["file_size_limit_bytes"],
        ),
        "nofile_limit": ulimits.get("nofile")
        == (contract_spec["open_files_limit"], contract_spec["open_files_limit"]),
        "single_workspace_mount": mount_contract,
        "mount_source_in_managed_root": runtime_workspace.parent == runtime_root,
        "no_docker_socket": all(
            mount.get("Destination") != "/var/run/docker.sock" for mount in mounts
        ),
        "no_case_mount": all(mount.get("Destination") != "/case" for mount in mounts),
        "scratch_tmpfs": expected_tmpfs_tokens.issubset(actual_tmpfs_tokens),
        "restart_disabled": restart_policy.get("Name") in {"", "no"},
        "no_sensitive_environment": not sensitive_env_names,
        "entrypoint": config.get("Entrypoint")
        == ["python3", "/opt/case08-runtime/idle.py"],
    }
    if not all(contract.values()):
        failed = sorted(key for key, passed in contract.items() if not passed)
        raise RuntimeError(f"sandbox_contract_failed:{','.join(failed)}")
    return {
        "contract": contract,
        "inspected_contract_sha256": canonical_hash(contract),
        "declared_sandbox_contract_sha256": contract_sha256,
        "container_state": state.get("Status"),
        "mount_count": len(mounts),
        "managed_runtime_root": runtime_root.as_posix(),
        "sensitive_environment_name_count": len(sensitive_env_names),
    }


def start_if_needed(container_id: str) -> None:
    raw = require_docker(["inspect", "--format", "{{.State.Status}}", container_id])
    if raw.strip() != "running":
        require_docker(["start", container_id])


def top_is_clean(container_id: str) -> bool:
    raw = require_docker(["top", container_id, "-eo", "pid,args"])
    processes = [
        line.strip().split(maxsplit=1)[1]
        for line in raw.splitlines()[1:]
        if len(line.strip().split(maxsplit=1)) == 2
    ]
    return len(processes) == 1 and processes[0].endswith(
        "python3 /opt/case08-runtime/idle.py"
    )


def quiesce_after_candidate_call(container_id: str) -> bool:
    """Kill candidate descendants before the host inspects candidate-controlled files."""

    if top_is_clean(container_id):
        return True
    require_docker(["restart", "--time", "2", container_id], timeout=15)
    if not top_is_clean(container_id):
        raise RuntimeError("candidate_process_quiescence_failed")
    return False


def restart_clean(
    container_id: str,
    *,
    phase: str,
    create_orphan: bool,
) -> dict[str, Any]:
    start_if_needed(container_id)
    sentinel = f"/scratch/{phase}_sentinel"
    seed_code = (
        "from pathlib import Path; "
        f"Path('{sentinel}').write_text('sentinel', encoding='utf-8')"
    )
    if create_orphan:
        seed_code += "; import subprocess; subprocess.Popen(['sleep', '300'])"
    require_docker(["exec", container_id, "python3", "-c", seed_code])
    require_docker(["restart", "--time", "2", container_id], timeout=15)
    inspect = docker(
        [
            "exec",
            container_id,
            "python3",
            "-c",
            (
                "from pathlib import Path; "
                f"raise SystemExit(1 if Path('{sentinel}').exists() else 0)"
            ),
        ]
    )
    scratch_cleared = inspect.returncode == 0
    processes_cleared = top_is_clean(container_id)
    if not scratch_cleared or not processes_cleared:
        raise RuntimeError(f"restart_isolation_failed:{phase}")
    return {
        "phase": phase,
        "scratch_cleared": scratch_cleared,
        "processes_cleared": processes_cleared,
        "exact_id_restart": True,
    }


def clear_directory(path: Path) -> None:
    resolved = path.resolve(strict=True)
    if len(resolved.parts) < 8 or resolved.name in {"", ".", ".."}:
        raise ValueError("runtime workspace path is too broad")
    for child in resolved.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            raise ValueError("unsupported runtime workspace entry")


def copy_submitted_workspace(
    submitted: Path,
    runtime: Path,
    *,
    owner_uid: int,
    owner_gid: int,
) -> None:
    clear_directory(runtime)
    shutil.copytree(submitted, runtime, symlinks=False, dirs_exist_ok=True)
    os.chown(runtime, owner_uid, owner_gid)
    for path in runtime.rglob("*"):
        if path.is_symlink():
            raise ValueError("copied runtime workspace contains a symbolic link")
        os.chown(path, owner_uid, owner_gid)


def static_checks(workspace: Path, fixture_root: Path) -> list[Check]:
    fixture_files = file_map(fixture_root)
    workspace_files = file_map(workspace)
    missing = sorted(set(fixture_files) - set(workspace_files))
    unexpected = sorted(
        set(workspace_files) - set(fixture_files) - {"state", "state/service.db"}
    )
    changed_protected = sorted(
        name
        for name, digest in fixture_files.items()
        if name != "nami_service/users.py" and workspace_files.get(name) != digest
    )
    return [
        Check(
            "workspace_input_scope",
            not missing and not unexpected,
            "submitted workspace inventory matches public fixture plus state database"
            if not missing and not unexpected
            else "submitted workspace inventory is outside the public contract",
        ),
        Check(
            "protected_inputs",
            not changed_protected,
            "protected input files are unchanged"
            if not changed_protected
            else "a protected input file changed",
        ),
        Check(
            "candidate_source_regular",
            workspace_files.get("nami_service/users.py") not in {None, "SYMLINK"},
            "candidate source is a regular workspace file",
        ),
    ]


def bounded_exec(
    container_id: str,
    call_id: str,
    request: dict[str, Any],
    *,
    timeout_seconds: float = 8,
) -> tuple[RunnerCall, dict[str, Any] | None]:
    process = subprocess.Popen(
        [
            "docker",
            "exec",
            "-i",
            container_id,
            "python3",
            "/opt/case08-runtime/adapter.py",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    encoded_request = json.dumps(request, sort_keys=True).encode("utf-8")
    process.stdin.write(encoded_request)
    process.stdin.close()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    deadline = time.monotonic() + timeout_seconds
    status = "completed"
    while process.poll() is None:
        if time.monotonic() >= deadline:
            status = "timeout"
            os.killpg(process.pid, signal.SIGKILL)
            break
        for key, _mask in selector.select(timeout=0.1):
            chunk = os.read(key.fileobj.fileno(), 65_536)
            if chunk:
                output.extend(chunk)
            if len(output) > MAX_EXEC_OUTPUT_BYTES:
                status = "output_limit"
                os.killpg(process.pid, signal.SIGKILL)
                break
        if status != "completed":
            break
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
    remaining = process.stdout.read(MAX_EXEC_OUTPUT_BYTES + 1 - len(output))
    if remaining:
        output.extend(remaining)
    if len(output) > MAX_EXEC_OUTPUT_BYTES:
        output = output[:MAX_EXEC_OUTPUT_BYTES]
        status = "output_limit"
    processes_were_clean = quiesce_after_candidate_call(container_id)
    if not processes_were_clean and status == "completed":
        status = "process_leak"
    payload: dict[str, Any] | None = None
    if status == "completed":
        for line in reversed(output.decode("utf-8", errors="replace").splitlines()):
            if not line.startswith(RESULT_PREFIX):
                continue
            try:
                candidate = json.loads(line[len(RESULT_PREFIX) :])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                payload = candidate
                break
        if payload is None:
            status = "protocol_error"
    call = RunnerCall(
        call_id=call_id,
        status=status,
        exit_code=process.returncode,
        output_bytes=len(output),
        output_sha256=hashlib.sha256(output).hexdigest(),
    )
    return call, payload


def payload_body(envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {}
    value = envelope.get("payload")
    return value if isinstance(value, dict) else {}


def unique_columns(connection: sqlite3.Connection) -> set[tuple[str, ...]]:
    columns: set[tuple[str, ...]] = set()
    for row in connection.execute("PRAGMA index_list('users')").fetchall():
        if int(row[2]) != 1:
            continue
        names = tuple(
            str(item[2])
            for item in connection.execute(
                f"PRAGMA index_info('{row[1]}')"
            ).fetchall()
        )
        columns.add(names)
    return columns


def row_count(database: Path, table: str) -> int:
    require_regular_runtime_file(database.parents[1], database)
    connection = sqlite3.connect(database)
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        connection.close()


def require_regular_runtime_file(runtime: Path, path: Path) -> None:
    """Reject symlinks and special files before trusted host-side parsing."""

    root = Path(os.path.abspath(os.fspath(runtime)))
    candidate = Path(os.path.abspath(os.fspath(path)))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("runtime file is outside managed workspace") from exc
    current = root
    root_mode = current.lstat().st_mode
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ValueError("managed runtime root is not a real directory")
    for index, part in enumerate(relative.parts):
        current /= part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("runtime file path contains a symbolic link")
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(mode):
            raise ValueError("runtime file parent is not a directory")
    if not stat.S_ISREG(current.lstat().st_mode):
        raise ValueError("runtime file is not a regular file")


def require_completed_call(checks: list[Check], call: RunnerCall) -> bool:
    if call.status == "completed":
        return True
    if call.status == "process_leak":
        checks.append(
            Check(
                "candidate_process_quiescence",
                False,
                "candidate descendant process was killed before host-side inspection",
            )
        )
    checks.append(Check("candidate_runtime", False, call.status))
    return False


def password_hash_ok(encoded: str, password: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, expected_hex = encoded.split("$", 3)
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
    except (TypeError, ValueError):
        return False
    if algorithm != "pbkdf2_sha256" or iterations != 120_000:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    ).hex()
    return actual == expected_hex


def dynamic_checks(
    container_id: str,
    runtime: Path,
) -> tuple[list[Check], list[RunnerCall], dict[str, Any]]:
    checks: list[Check] = []
    calls: list[RunnerCall] = []
    derived: dict[str, Any] = {}
    database = runtime / "state" / "service.db"

    auth_call, auth_envelope = bounded_exec(
        container_id,
        "existing_authentication",
        {
            "operation": "authenticate",
            "identifier": "ALICE",
            "password": "ExistingPass9",
        },
    )
    calls.append(auth_call)
    auth_payload = payload_body(auth_envelope)
    if not require_completed_call(checks, auth_call):
        return checks, calls, derived
    auth_ok = auth_payload.get("ok") is True and auth_payload.get("value") is True
    checks.append(
        Check(
            "existing_authentication",
            auth_ok,
            "seeded authentication remains functional"
            if auth_ok
            else "seeded authentication regressed",
        )
    )

    register_call, register_envelope = bounded_exec(
        container_id,
        "valid_registration",
        {
            "operation": "register",
            "username": "  Nova_User  ",
            "email": "NOVA@Example.Test ",
            "password": "StrongPass9",
            "created_at": "2026-07-20T01:00:00Z",
        },
    )
    calls.append(register_call)
    if not require_completed_call(checks, register_call):
        return checks, calls, derived
    register_payload = payload_body(register_envelope)
    public_value = register_payload.get("public_value")
    registration_ok = (
        register_call.status == "completed"
        and register_payload.get("ok") is True
        and register_payload.get("keys")
        == ["created_at", "email", "id", "username"]
        and isinstance(public_value, dict)
        and public_value.get("username") == "Nova_User"
        and public_value.get("email") == "nova@example.test"
        and public_value.get("created_at") == "2026-07-20T01:00:00Z"
    )
    checks.append(
        Check(
            "valid_registration",
            registration_ok,
            "valid registration returned the public contract"
            if registration_ok
            else "valid registration failed or returned private fields",
        )
    )

    require_regular_runtime_file(runtime, database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            ("nova_user",),
        ).fetchone()
        audit = connection.execute(
            "SELECT event_type FROM audit_events WHERE user_id = ?",
            (row["id"] if row else -1,),
        ).fetchall()
        stored_hash = str(row["password_hash"]) if row else ""
        hash_ok = bool(
            row
            and stored_hash != "StrongPass9"
            and password_hash_ok(stored_hash, "StrongPass9")
            and b"StrongPass9" not in database.read_bytes()
        )
        audit_ok = len(audit) == 1 and audit[0]["event_type"] == "user.registered"
        schema_ok = {("username",), ("email",)}.issubset(unique_columns(connection))
    finally:
        connection.close()
    checks.extend(
        [
            Check("password_storage", hash_ok, "password storage checked externally"),
            Check("audit_event", audit_ok, "single registration audit checked externally"),
            Check("database_unique_constraints", schema_ok, "unique indexes checked externally"),
        ]
    )

    before_conflicts = row_count(database, "users")
    conflict_types: list[str] = []
    for index, candidate in enumerate(
        [
            ("nova_user", "other@example.test"),
            ("Other_User", "NOVA@EXAMPLE.TEST"),
        ],
        start=1,
    ):
        call, envelope = bounded_exec(
            container_id,
            f"conflict_{index}",
            {
                "operation": "register",
                "username": candidate[0],
                "email": candidate[1],
                "password": "OtherPass9A",
            },
        )
        calls.append(call)
        if not require_completed_call(checks, call):
            return checks, calls, derived
        conflict_types.append(str(payload_body(envelope).get("exception_type")))
    conflicts_ok = (
        conflict_types == ["RegistrationConflict", "RegistrationConflict"]
        and row_count(database, "users") == before_conflicts
    )
    checks.append(
        Check(
            "case_insensitive_conflicts",
            conflicts_ok,
            "duplicate username and email were rejected without writes",
        )
    )

    before_invalid = row_count(database, "users")
    invalid_types: list[str] = []
    invalid_inputs = [
        ("1x", "valid@example.test", "StrongPass9"),
        ("Valid_User", "broken-email", "StrongPass9"),
        ("Valid_User", "valid@example.test", "weakpass"),
    ]
    for index, candidate in enumerate(invalid_inputs, start=1):
        call, envelope = bounded_exec(
            container_id,
            f"invalid_input_{index}",
            {
                "operation": "register",
                "username": candidate[0],
                "email": candidate[1],
                "password": candidate[2],
            },
        )
        calls.append(call)
        if not require_completed_call(checks, call):
            return checks, calls, derived
        invalid_types.append(str(payload_body(envelope).get("exception_type")))
    invalid_ok = (
        invalid_types == ["RegistrationValidationError"] * 3
        and row_count(database, "users") == before_invalid
    )
    checks.append(
        Check(
            "invalid_input_rejection",
            invalid_ok,
            "invalid inputs were rejected without database writes",
        )
    )

    require_regular_runtime_file(runtime, database)
    trigger_connection = sqlite3.connect(database)
    try:
        trigger_connection.execute(
            """
            CREATE TRIGGER reject_registration_audit
            BEFORE INSERT ON audit_events
            WHEN NEW.event_type = 'user.registered'
            BEGIN SELECT RAISE(ABORT, 'synthetic audit failure'); END
            """
        )
        trigger_connection.commit()
    finally:
        trigger_connection.close()
    rollback_call, rollback_envelope = bounded_exec(
        container_id,
        "transaction_rollback",
        {
            "operation": "register",
            "username": "Rollback_User",
            "email": "rollback@example.test",
            "password": "RollbackPass9",
        },
    )
    calls.append(rollback_call)
    if not require_completed_call(checks, rollback_call):
        return checks, calls, derived
    require_regular_runtime_file(runtime, database)
    cleanup_connection = sqlite3.connect(database)
    try:
        rollback_count = int(
            cleanup_connection.execute(
                "SELECT COUNT(*) FROM users WHERE username = ? COLLATE NOCASE",
                ("Rollback_User",),
            ).fetchone()[0]
        )
        cleanup_connection.execute("DROP TRIGGER reject_registration_audit")
        cleanup_connection.commit()
    finally:
        cleanup_connection.close()
    rollback_ok = (
        payload_body(rollback_envelope).get("ok") is False and rollback_count == 0
    )
    checks.append(
        Check(
            "transaction_rollback",
            rollback_ok,
            "audit failure left no partial user record",
        )
    )

    public_call, public_envelope = bounded_exec(
        container_id,
        "public_tests",
        {"operation": "public_tests"},
        timeout_seconds=35,
    )
    calls.append(public_call)
    if not require_completed_call(checks, public_call):
        return checks, calls, derived
    public_ok = (
        public_call.status == "completed"
        and payload_body(public_envelope).get("ok") is True
    )
    checks.append(Check("public_tests", public_ok, "public tests executed in sandbox"))
    require_regular_runtime_file(runtime, database)
    final_connection = sqlite3.connect(database)
    try:
        application_tables = {
            str(row[0])
            for row in final_connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }
        triggers = final_connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
        user_count = int(
            final_connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        )
        audit_types = sorted(
            str(row[0])
            for row in final_connection.execute(
                "SELECT event_type FROM audit_events"
            ).fetchall()
        )
        integrity = str(final_connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = final_connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        final_connection.close()
    database_scope_ok = (
        application_tables == {"users", "audit_events"}
        and not triggers
        and user_count == 2
        and audit_types == ["user.registered", "user.seeded"]
        and integrity == "ok"
        and not foreign_key_violations
    )
    checks.append(
        Check(
            "database_side_effect_scope",
            database_scope_ok,
            "database contains only the required user and audit state"
            if database_scope_ok
            else "database contains contract-external schema or row side effects",
        )
    )
    derived["database_final_state"] = {
        "application_tables": sorted(application_tables),
        "trigger_count": len(triggers),
        "user_count": user_count,
        "audit_types": audit_types,
        "integrity": integrity,
        "foreign_key_violation_count": len(foreign_key_violations),
    }
    return checks, calls, derived


def runtime_scope_checks(
    submitted: Path,
    runtime: Path,
) -> tuple[list[Check], dict[str, Any]]:
    submitted_files = file_map(submitted)
    runtime_files = file_map(runtime)
    unexpected = sorted(set(runtime_files) - set(submitted_files))
    missing = sorted(set(submitted_files) - set(runtime_files))
    changed = sorted(
        name
        for name in set(runtime_files).intersection(submitted_files)
        if name != "state/service.db" and runtime_files[name] != submitted_files[name]
    )
    max_file_size = max(
        (
            path.lstat().st_size
            for path in runtime.rglob("*")
            if stat.S_ISREG(path.lstat().st_mode)
        ),
        default=0,
    )
    checks = [
        Check(
            "runtime_workspace_scope",
            not unexpected and not missing and not changed,
            "candidate runtime changed only the authorized state database"
            if not unexpected and not missing and not changed
            else "candidate runtime added, deleted or changed contract-external files",
        ),
        Check(
            "workspace_file_size_limit",
            max_file_size <= MAX_WORKSPACE_FILE_BYTES,
            "all candidate files remain within the configured fsize limit",
        ),
    ]
    derived: dict[str, Any] = {
        "runtime_unexpected_file_count": len(unexpected),
        "runtime_missing_file_count": len(missing),
        "runtime_changed_protected_file_count": len(changed),
        "runtime_unexpected_files": unexpected,
        "runtime_missing_files": missing,
        "runtime_changed_protected_files": changed,
        "runtime_max_file_size": max_file_size,
    }

    probe_path = runtime / "probe_report.json"
    if probe_path.is_file() and probe_path.stat().st_size <= 65_536:
        try:
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            probe = {}
        if isinstance(probe, dict):
            hidden_readable = bool(probe.get("hidden_readable"))
            credential_readable = bool(probe.get("credential_readable"))
            host_process_visible = bool(probe.get("host_process_visible"))
            docker_socket_visible = bool(probe.get("docker_socket_visible"))
            checks.append(
                Check(
                    "security_probe_isolated",
                    not any(
                        (
                            hidden_readable,
                            credential_readable,
                            host_process_visible,
                            docker_socket_visible,
                        )
                    ),
                    "probe found no hidden case content, credential, host process or Docker socket",
                )
            )
            derived["security_probe"] = {
                "hidden_readable": hidden_readable,
                "credential_readable": credential_readable,
                "host_process_visible": host_process_visible,
                "docker_socket_visible": docker_socket_visible,
                "attempted_path_count": int(probe.get("attempted_path_count", 0)),
            }

    oversize_path = runtime / "oversize_probe.json"
    if oversize_path.is_file() and oversize_path.stat().st_size <= 65_536:
        try:
            oversize = json.loads(oversize_path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            oversize = {}
        if isinstance(oversize, dict):
            limit_triggered = oversize.get("limit_triggered") is True
            checks.append(
                Check(
                    "oversize_write_blocked",
                    limit_triggered and max_file_size <= MAX_WORKSPACE_FILE_BYTES,
                    "candidate write beyond 64 MiB was blocked by RLIMIT_FSIZE",
                )
            )
            derived["oversize_probe"] = {
                "limit_triggered": limit_triggered,
                "bytes_written": int(oversize.get("bytes_written", 0)),
            }
    return checks, derived


def write_result(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    next_path = path.with_name(path.name + ".next")
    next_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    next_path.replace(path)


def main() -> int:
    args = parse_args()
    submitted = args.submitted_workspace.resolve(strict=True)
    _runtime_root, runtime = managed_runtime_paths(
        args.runtime_root,
        args.runtime_workspace,
    )
    fixture_root = args.fixture_root.resolve(strict=True)
    contract_spec, _contract_sha256 = read_contract(args.sandbox_contract)
    owner_uid, owner_gid = (
        int(value) for value in str(contract_spec["user"]).split(":", 1)
    )
    submitted_before = workspace_sha256(submitted)
    checks = static_checks(submitted, fixture_root)
    calls: list[RunnerCall] = []
    derived: dict[str, Any] = {}
    pre_restart: dict[str, Any] | None = None
    post_restart: dict[str, Any] | None = None
    inspection = inspect_contract(args)
    checks.append(Check("sandbox_contract", True, "exact sandbox contract inspected"))
    try:
        pre_restart = restart_clean(
            args.container_id,
            phase="before_attempt",
            create_orphan=True,
        )
        copy_submitted_workspace(
            submitted,
            runtime,
            owner_uid=owner_uid,
            owner_gid=owner_gid,
        )
        dynamic, calls, dynamic_derived = dynamic_checks(args.container_id, runtime)
        checks.extend(dynamic)
        derived.update(dynamic_derived)
        runtime_checks, runtime_derived = runtime_scope_checks(submitted, runtime)
        checks.extend(runtime_checks)
        derived.update(runtime_derived)
    except Exception as exc:  # noqa: BLE001 - result must preserve a failed attempt
        checks.append(
            Check(
                "controller_runtime",
                False,
                f"controller failed closed with {type(exc).__name__}",
            )
        )
    finally:
        try:
            post_restart = restart_clean(
                args.container_id,
                phase="after_attempt",
                create_orphan=False,
            )
        except Exception as exc:  # noqa: BLE001 - cleanup failure is a hard gate
            checks.append(
                Check(
                    "post_attempt_cleanup",
                    False,
                    f"post-attempt restart failed with {type(exc).__name__}",
                )
            )
    submitted_after = workspace_sha256(submitted)
    nonmutation = submitted_before == submitted_after
    checks.append(
        Check(
            "verifier_non_mutation",
            nonmutation,
            "hidden verification did not modify the submitted workspace"
            if nonmutation
            else "hidden verification modified the submitted workspace",
        )
    )
    accepted = bool(checks) and all(check.passed for check in checks)
    result = {
        "schema_version": "case08_isolated_verifier_result_v2",
        "attempt_id": args.attempt_id,
        "accepted": accepted,
        "score": sum(check.passed for check in checks) / len(checks),
        "checks": [asdict(check) for check in checks],
        "initial_state_sha256": args.initial_state_sha256,
        "final_state_sha256": submitted_after,
        "sandbox": {
            "container_id": args.container_id,
            "container_name": args.container_name,
            "image_id": args.image_id,
            "inspection": inspection,
            "pre_restart": pre_restart,
            "post_restart": post_restart,
        },
        "runner_calls": [asdict(call) for call in calls],
        "derived_evidence": derived,
    }
    write_result(args.output, result)
    print(
        json.dumps(
            {
                "accepted": accepted,
                "passed_checks": sum(check.passed for check in checks),
                "total_checks": len(checks),
            },
            sort_keys=True,
        )
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
