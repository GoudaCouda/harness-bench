#!/usr/bin/env python3
"""受信控制器：在有界、静默且可审计的 Docker sandbox 中执行候选脚本。"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


STABLE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,80}$")
PLAN_SCHEMA = "case11_execution_ownership_plan_v2"
CONTRACT_SCHEMA = "case11_static_sandbox_contract_v2"
RECORD_SCHEMA = "case11_container_record_v2"
RESULT_SCHEMA = "case11_sandbox_result_v2"


class ContractError(RuntimeError):
    pass


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ContractError("JSON 文件必须是非链接普通文件")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("JSON 根必须是对象")
    return value


def run_bytes(command: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def tail_text(data: bytes, limit: int) -> str:
    return data[-limit:].decode("utf-8", errors="replace")


def docker_json(container_id: str) -> dict[str, Any]:
    completed = run_bytes(["docker", "inspect", container_id], timeout=10)
    if completed.returncode != 0:
        raise ContractError("docker inspect 失败")
    value = json.loads(completed.stdout.decode("utf-8"))
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ContractError("docker inspect 结构无效")
    return value[0]


def ensure_no_symlink_ancestors(path: Path, boundary: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise ContractError("路径或其父级不得是符号链接")
        if current == boundary:
            return
        if boundary not in current.parents:
            raise ContractError("路径越出动态运行根")
        current = current.parent


def validate_plan(
    plan_path: Path,
    plan: dict[str, Any],
    contract_path: Path,
    contract: dict[str, Any],
) -> tuple[Path, Path, Path, Path]:
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ContractError("ownership plan 版本无效")
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise ContractError("sandbox contract 版本无效")
    if contract.get("ephemeral_runtime_write_exceptions") != [
        {
            "path": "/dev/shm",
            "max_bytes": 4096,
            "persistence": "discarded_with_container",
            "purpose": "python_runtime_only",
        }
    ] or contract.get("shm_bytes") != 4096:
        raise ContractError("临时运行时写入例外与 shm 上限不一致")
    if contract.get("memory_swap_bytes") != contract.get("memory_bytes"):
        raise ContractError("memory-swap 必须与 memory 相等以禁止额外 swap")
    if plan.get("contract_sha256") != sha256_file(contract_path):
        raise ContractError("ownership plan 未锁定当前 sandbox contract")
    if plan_path.name != "ownership_plan.json" or plan_path.parent.name != "control":
        raise ContractError("ownership plan 必须位于运行根的 control/ownership_plan.json")
    runtime_root = plan_path.parent.parent.resolve(strict=True)
    if runtime_root == Path("/") or len(runtime_root.parts) < 5:
        raise ContractError("动态运行根过于宽泛")
    ensure_no_symlink_ancestors(plan_path, runtime_root)
    if Path(str(plan.get("runtime_root", ""))).resolve(strict=True) != runtime_root:
        raise ContractError("runtime_root 与 plan 所在位置不一致")
    attempts_root = Path(str(plan.get("attempts_root", ""))).resolve(strict=True)
    evidence_root = Path(str(plan.get("evidence_root", ""))).resolve(strict=True)
    if attempts_root != runtime_root / "attempts" or evidence_root != runtime_root / "evidence":
        raise ContractError("动态子目录必须是运行根的固定直接子目录")
    ensure_no_symlink_ancestors(attempts_root, runtime_root)
    ensure_no_symlink_ancestors(evidence_root, runtime_root)
    resource_manifest = Path(str(plan.get("resource_manifest_path", ""))).resolve(strict=True)
    if resource_manifest.name != "resource_manifest.json" or resource_manifest.parent.name != "case_11":
        raise ContractError("resource manifest 路径无效")
    labels = plan.get("labels")
    required = set(contract.get("required_labels", [])) - {"agent_sft.attempt_id"}
    if not isinstance(labels, dict) or set(labels) != required:
        raise ContractError("动态 labels 必须与静态合同完全一致")
    for key, value in labels.items():
        if key == "agent_sft.purpose":
            if value != "nami_work_gold20":
                raise ContractError("purpose label 无效")
        elif not isinstance(value, str) or not STABLE.fullmatch(value):
            raise ContractError(f"label {key} 无效")
    if plan.get("image_digest") != contract.get("image_digest"):
        raise ContractError("plan 和 contract 的镜像摘要不一致")
    return runtime_root, attempts_root, evidence_root, resource_manifest


def _object_identity(status: os.stat_result) -> tuple[int, int, int]:
    return status.st_dev, status.st_ino, stat.S_IFMT(status.st_mode)


def _file_snapshot(status: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        status.st_dev,
        status.st_ino,
        stat.S_IFMT(status.st_mode),
        status.st_size,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _safe_open_flags(*, directory: bool = False) -> int:
    required = ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required):
        raise ContractError("当前平台缺少安全 inventory 所需的 open 标志")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    if directory:
        if not hasattr(os, "O_DIRECTORY"):
            raise ContractError("当前平台缺少 O_DIRECTORY")
        flags |= os.O_DIRECTORY
    return flags


def _secure_hash_regular_at(
    directory_fd: int,
    name: str,
    observed: os.stat_result,
    max_single: int,
) -> tuple[str | None, str | None]:
    """通过不跟随且非阻塞的 fd 哈希一个静态普通文件。

    返回 ``(sha256, error_code)``。任何对象替换、内容变化、提前 EOF、
    消失或类型改变都会 fail closed；读取量绝不超过事前确认的
    ``st_size``，而 ``st_size`` 必须不大于单文件上限。
    """

    if not stat.S_ISREG(observed.st_mode):
        return None, "not_regular"
    if observed.st_size < 0 or observed.st_size > max_single:
        return None, "single_file_limit"
    try:
        descriptor = os.open(name, _safe_open_flags(), dir_fd=directory_fd)
    except FileNotFoundError:
        return None, "vanished"
    except OSError:
        return None, "open_failed"
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _file_snapshot(opened) != _file_snapshot(observed):
            return None, "changed_before_read"
        digest = hashlib.sha256()
        remaining = opened.st_size
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                return None, "short_read"
            digest.update(block)
            remaining -= len(block)
        after_read = os.fstat(descriptor)
        if _file_snapshot(after_read) != _file_snapshot(opened):
            return None, "changed_during_read"
        try:
            still_named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None, "vanished_after_read"
        if _file_snapshot(still_named) != _file_snapshot(after_read):
            return None, "replaced_after_read"
        return digest.hexdigest(), None
    finally:
        os.close(descriptor)


def bounded_inventory(
    root: Path,
    contract: dict[str, Any],
    *,
    hash_regular: bool,
    tolerate_disappeared: bool,
) -> dict[str, Any]:
    max_bytes = int(contract["max_workspace_bytes"])
    max_entries = int(contract["max_workspace_entries"])
    max_single = int(contract["file_size_bytes"])
    entries: list[dict[str, Any]] = []
    total = 0
    stack: list[tuple[int, str]] = []
    exceeded_entries = False
    exceeded_bytes = False
    exceeded_single_file = False
    scan_error = False
    unsafe_entry = False
    race_detected = False
    volatile_entry_count = 0
    try:
        root_fd = os.open(root, _safe_open_flags(directory=True))
    except OSError:
        root_fd = -1
        scan_error = True
    if root_fd >= 0:
        try:
            root_status = os.fstat(root_fd)
            if not stat.S_ISDIR(root_status.st_mode):
                scan_error = True
            else:
                stack.append((root_fd, ""))
                root_fd = -1
            while stack and not (exceeded_entries or exceeded_bytes or exceeded_single_file):
                directory_fd, directory_relative = stack.pop()
                try:
                    try:
                        iterator = os.scandir(directory_fd)
                    except OSError:
                        entries.append({"path": directory_relative or ".", "kind": "unreadable"})
                        scan_error = True
                        break
                    with iterator:
                        for item in iterator:
                            relative = f"{directory_relative}/{item.name}" if directory_relative else item.name
                            try:
                                status = os.stat(item.name, dir_fd=directory_fd, follow_symlinks=False)
                            except FileNotFoundError:
                                volatile_entry_count += 1
                                if not tolerate_disappeared:
                                    entries.append({"path": relative, "kind": "vanished"})
                                    scan_error = True
                                    race_detected = True
                                    break
                                continue
                            except OSError:
                                entries.append({"path": relative, "kind": "unreadable"})
                                scan_error = True
                                break
                            mode = stat.S_IMODE(status.st_mode)
                            if stat.S_ISLNK(status.st_mode):
                                record: dict[str, Any] = {"path": relative, "kind": "symlink", "mode": mode}
                                unsafe_entry = True
                            elif stat.S_ISDIR(status.st_mode):
                                record = {"path": relative, "kind": "directory", "mode": mode}
                                try:
                                    child_fd = os.open(
                                        item.name,
                                        _safe_open_flags(directory=True),
                                        dir_fd=directory_fd,
                                    )
                                except FileNotFoundError:
                                    volatile_entry_count += 1
                                    if not tolerate_disappeared:
                                        record["inventory_error"] = "directory_vanished"
                                        scan_error = True
                                        race_detected = True
                                except OSError:
                                    record["inventory_error"] = "directory_open_failed"
                                    scan_error = True
                                    race_detected = True
                                else:
                                    opened_status = os.fstat(child_fd)
                                    if _object_identity(opened_status) != _object_identity(status):
                                        os.close(child_fd)
                                        record["inventory_error"] = "directory_replaced"
                                        scan_error = True
                                        race_detected = True
                                    else:
                                        stack.append((child_fd, relative))
                            elif stat.S_ISREG(status.st_mode):
                                total += status.st_size
                                record = {
                                    "path": relative,
                                    "kind": "file",
                                    "mode": mode,
                                    "size_bytes": status.st_size,
                                    "link_count": status.st_nlink,
                                }
                                if status.st_size > max_single:
                                    exceeded_single_file = True
                                    record["inventory_error"] = "single_file_limit"
                                elif hash_regular and total <= max_bytes:
                                    file_hash, hash_error = _secure_hash_regular_at(
                                        directory_fd,
                                        item.name,
                                        status,
                                        max_single,
                                    )
                                    if hash_error is None:
                                        record["sha256"] = file_hash
                                    else:
                                        record["inventory_error"] = hash_error
                                        scan_error = True
                                        race_detected = True
                            elif stat.S_ISFIFO(status.st_mode):
                                record = {"path": relative, "kind": "fifo", "mode": mode}
                                unsafe_entry = True
                            elif stat.S_ISSOCK(status.st_mode):
                                record = {"path": relative, "kind": "socket", "mode": mode}
                                unsafe_entry = True
                            elif stat.S_ISCHR(status.st_mode) or stat.S_ISBLK(status.st_mode):
                                record = {"path": relative, "kind": "device", "mode": mode}
                                unsafe_entry = True
                            else:
                                record = {"path": relative, "kind": "other", "mode": mode}
                                unsafe_entry = True
                            entries.append(record)
                            if len(entries) > max_entries:
                                exceeded_entries = True
                                break
                            if total > max_bytes:
                                exceeded_bytes = True
                                break
                            if scan_error or unsafe_entry or exceeded_single_file:
                                break
                finally:
                    os.close(directory_fd)
                if scan_error or unsafe_entry:
                    break
        finally:
            if root_fd >= 0:
                os.close(root_fd)
            for descriptor, _ in stack:
                os.close(descriptor)
    entries.sort(key=lambda item: str(item["path"]))
    digest = hashlib.sha256(
        json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "entries": entries,
        "entry_count": len(entries),
        "total_file_bytes": total,
        "entry_limit_exceeded": exceeded_entries,
        "byte_limit_exceeded": exceeded_bytes,
        "single_file_limit_exceeded": exceeded_single_file,
        "unsafe_entry_detected": unsafe_entry,
        "scan_error": scan_error,
        "race_detected": race_detected,
        "volatile_entry_count": volatile_entry_count,
        "hash_mode": "secure_fd" if hash_regular else "metadata_only",
        "inventory_sha256": digest,
    }


def expected_create_args(
    contract: dict[str, Any],
    plan: dict[str, Any],
    attempt_dir: Path,
    attempt_id: str,
    container_name: str,
) -> list[str]:
    labels = dict(plan["labels"])
    labels["agent_sft.attempt_id"] = attempt_id
    output_dir = attempt_dir / "output"
    arguments = [
        "docker",
        "create",
        "--name",
        container_name,
        "--network",
        str(contract["network_mode"]),
        "--read-only",
        "--user",
        str(contract["container_user"]),
        "--workdir",
        str(contract["workdir"]),
        "--cpus",
        str(contract["cpu_cores"]),
        "--memory",
        str(contract["memory_bytes"]),
        "--memory-swap",
        str(contract["memory_swap_bytes"]),
        "--pids-limit",
        str(contract["pids_limit"]),
        "--shm-size",
        str(contract["shm_bytes"]),
        "--ulimit",
        f"fsize={contract['file_size_bytes']}:{contract['file_size_bytes']}",
        "--ulimit",
        f"nofile={contract['nofile']}:{contract['nofile']}",
        "--stop-timeout",
        str(contract["stop_timeout_seconds"]),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--restart",
        "no",
        "--init",
        "--log-driver",
        str(contract["log_driver"]["name"]),
        "--log-opt",
        f"max-size={contract['log_driver']['max_size']}",
        "--log-opt",
        f"max-file={contract['log_driver']['max_file']}",
        "--mount",
        f"type=bind,src={attempt_dir},dst={contract['workspace_destination']},readonly",
        "--mount",
        f"type=bind,src={output_dir},dst={contract['workspace_destination']}/output",
    ]
    for key in sorted(contract["environment"]):
        arguments.extend(["--env", f"{key}={contract['environment'][key]}"])
    for key in sorted(labels):
        arguments.extend(["--label", f"{key}={labels[key]}"])
    arguments.append(str(contract["image_digest"]))
    arguments.extend(str(item) for item in contract["command"])
    return arguments


def inspect_contract(
    value: dict[str, Any],
    contract: dict[str, Any],
    plan: dict[str, Any],
    attempt_dir: Path,
    attempt_id: str,
    *,
    require_stopped: bool,
) -> list[str]:
    errors: list[str] = []
    config = value.get("Config", {})
    host = value.get("HostConfig", {})
    state = value.get("State", {})
    labels = dict(plan["labels"])
    labels["agent_sft.attempt_id"] = attempt_id
    if config.get("Image") != contract["image_digest"]:
        errors.append("image")
    if config.get("User") != contract["container_user"]:
        errors.append("user")
    if config.get("WorkingDir") != contract["workdir"]:
        errors.append("workdir")
    if config.get("Labels") != labels:
        errors.append("labels")
    actual_env = {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in (config.get("Env") or [])
        if "=" in item
    }
    expected_env = {str(key): str(item) for key, item in contract["environment"].items()}
    allowed_env = set(expected_env) | set(contract["allowed_inherited_environment"])
    if any(actual_env.get(key) != item for key, item in expected_env.items()) or set(actual_env) - allowed_env:
        errors.append("environment")
    if config.get("Entrypoint") not in (None, []):
        errors.append("entrypoint")
    if config.get("Cmd") != contract["command"]:
        errors.append("command")
    if host.get("NetworkMode") != "none" or host.get("ReadonlyRootfs") is not True:
        errors.append("network_or_rootfs")
    if host.get("Privileged") is not False or host.get("CapDrop") != ["ALL"]:
        errors.append("privilege")
    if set(host.get("SecurityOpt") or []) not in ({"no-new-privileges"}, {"no-new-privileges=true"}):
        errors.append("security_opt")
    if host.get("NanoCpus") != int(contract["cpu_cores"] * 1_000_000_000):
        errors.append("cpu")
    if (
        host.get("Memory") != contract["memory_bytes"]
        or host.get("MemorySwap") != contract["memory_swap_bytes"]
        or host.get("PidsLimit") != contract["pids_limit"]
    ):
        errors.append("memory_or_pids")
    if host.get("ShmSize") != contract["shm_bytes"]:
        errors.append("shm")
    expected_ulimits = {
        ("fsize", int(contract["file_size_bytes"]), int(contract["file_size_bytes"])),
        ("nofile", int(contract["nofile"]), int(contract["nofile"])),
    }
    actual_ulimits = {(item.get("Name"), item.get("Soft"), item.get("Hard")) for item in (host.get("Ulimits") or [])}
    if actual_ulimits != expected_ulimits:
        errors.append("ulimits")
    if host.get("Init") is not True or config.get("StopTimeout") != contract["stop_timeout_seconds"]:
        errors.append("init_or_stop_timeout")
    if (host.get("RestartPolicy") or {}).get("Name") != "no" or value.get("RestartCount") != 0:
        errors.append("restart")
    if host.get("PortBindings") not in (None, {}) or host.get("Devices") not in (None, []):
        errors.append("ports_or_devices")
    expected_log = {
        "Type": contract["log_driver"]["name"],
        "Config": {"max-size": contract["log_driver"]["max_size"], "max-file": contract["log_driver"]["max_file"]},
    }
    if host.get("LogConfig") != expected_log:
        errors.append("log_driver")
    mounts = value.get("Mounts")
    expected_mounts = {
        "/workspace": (attempt_dir, False),
        "/workspace/output": (attempt_dir / "output", True),
    }
    if not isinstance(mounts, list) or len(mounts) != 2:
        errors.append("mount_count")
    else:
        actual_mounts: dict[str, tuple[Path, bool]] = {}
        for mount in mounts:
            if mount.get("Type") != "bind":
                continue
            actual_mounts[str(mount.get("Destination"))] = (
                Path(str(mount.get("Source"))).resolve(),
                bool(mount.get("RW")),
            )
        if actual_mounts != expected_mounts:
            errors.append("mount_contract")
    if state.get("Restarting") is not False:
        errors.append("restarting")
    if require_stopped and (state.get("Running") is not False or state.get("Pid") != 0 or state.get("Status") not in {"exited", "dead"}):
        errors.append("not_quiescent")
    return errors


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.next")
    if temporary.exists() or temporary.is_symlink():
        raise ContractError("manifest 临时文件冲突")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o640)
    os.replace(temporary, path)


def update_resource_manifest(path: Path, operation: str, record: dict[str, Any]) -> None:
    lock_path = path.with_name(".resource_manifest.case11.lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o640)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        manifest = read_object(path)
        records = manifest.setdefault("container_creation_records", [])
        if not isinstance(records, list):
            raise ContractError("container_creation_records 无效")
        resources = manifest.setdefault("resources", {})
        containers = resources.setdefault("containers", []) if isinstance(resources, dict) else None
        if not isinstance(containers, list):
            raise ContractError("resources.containers 无效")
        record_id = str(record["creation_record_id"])
        matches = [item for item in records if isinstance(item, dict) and item.get("creation_record_id") == record_id]
        if operation == "plan":
            if matches:
                raise ContractError("容器创建计划 ID 已存在")
            records.append(record)
        elif operation in {"created", "failed"}:
            if len(matches) != 1:
                raise ContractError("容器创建计划记录不存在或不唯一")
            matches[0].update(record)
            if operation == "created":
                container_id = str(record["container_id"])
                container_name = str(record["container_name"])
                if any(
                    isinstance(item, dict)
                    and (item.get("container_id") == container_id or item.get("container_name") == container_name)
                    for item in containers
                ):
                    raise ContractError("精确容器资源重复")
                containers.append(
                    {
                        "attempt_id": record["attempt_id"],
                        "cleanup_allowed_after_results_persisted": True,
                        "container_id": container_id,
                        "container_name": container_name,
                        "invocation_id": record["invocation_id"],
                        "purpose": "case11_sandbox_validation",
                    }
                )
        else:
            raise ContractError("资源登记操作无效")
        manifest["updated_at"] = utc_now()
        atomic_json(path, manifest)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def append_record(path: Path, record: dict[str, Any]) -> None:
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def force_quiescent(container_id: str) -> dict[str, Any] | None:
    try:
        state = docker_json(container_id).get("State", {})
    except (ContractError, json.JSONDecodeError):
        return None
    if state.get("Running") is True or state.get("Restarting") is True:
        run_bytes(["docker", "kill", container_id], timeout=10)
    try:
        run_bytes(["docker", "wait", container_id], timeout=15)
    except subprocess.TimeoutExpired:
        run_bytes(["docker", "kill", container_id], timeout=10)
    try:
        return docker_json(container_id)
    except (ContractError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--invocation-id", required=True)
    args = parser.parse_args()
    container_id = ""
    container_name = ""
    result_path: Path | None = None
    attempt_dir: Path | None = None
    contract: dict[str, Any] = {}
    plan: dict[str, Any] = {}
    pre_errors: list[str] = []
    post_errors: list[str] = []
    before_tree: dict[str, Any] = {}
    after_tree: dict[str, Any] = {}
    candidate_exit: int | None = None
    timed_out = False
    quota_exceeded = False
    entry_limit_exceeded = False
    single_file_limit_exceeded = False
    unsafe_entry_detected = False
    log_limit_exceeded = False
    inventory_scan_failed = False
    controller_error = ""
    started_at = time.monotonic()
    started_container = False
    creation_planned = False
    resource_manifest: Path | None = None
    final_inspect: dict[str, Any] | None = None
    try:
        if not STABLE.fullmatch(args.attempt_id) or not STABLE.fullmatch(args.invocation_id):
            raise ContractError("attempt/invocation ID 无效")
        contract_path = args.contract.resolve(strict=True)
        plan_path = args.plan.resolve(strict=True)
        contract = read_object(contract_path)
        plan = read_object(plan_path)
        runtime_root, attempts_root, evidence_root, resource_manifest = validate_plan(plan_path, plan, contract_path, contract)
        attempt_dir = (attempts_root / args.attempt_id).resolve(strict=True)
        if attempt_dir.parent != attempts_root or attempt_dir.is_symlink() or not attempt_dir.is_dir():
            raise ContractError("attempt 必须是 attempts_root 的非链接直接子目录")
        ensure_no_symlink_ancestors(attempt_dir, runtime_root)
        output_dir = attempt_dir / "output"
        if output_dir.is_symlink() or not output_dir.is_dir():
            raise ContractError("output 必须是非链接目录")
        for relative in ("input/weekly_operations.csv", "input/metric_definitions.json", "input/brief_template.md", "submission/generate_brief.py"):
            path = attempt_dir / relative
            if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
                raise ContractError(f"执行前受保护文件无效：{relative}")
            if stat.S_IMODE(path.lstat().st_mode) & 0o022:
                raise ContractError(f"执行前受保护文件可被 group/other 写入：{relative}")
        result_path = evidence_root / f"{args.invocation_id}.sandbox.json"
        if result_path.exists() or result_path.is_symlink():
            raise ContractError("不得覆盖 sandbox 证据")
        parts = [plan["labels"]["agent_sft.run_id"], plan["labels"]["agent_sft.case_id"], args.invocation_id]
        container_name = "c11-" + "-".join(re.sub(r"[^a-z0-9_.-]+", "-", item) for item in parts)
        before_tree = bounded_inventory(
            attempt_dir,
            contract,
            hash_regular=True,
            tolerate_disappeared=False,
        )
        if (
            before_tree["byte_limit_exceeded"]
            or before_tree["entry_limit_exceeded"]
            or before_tree["single_file_limit_exceeded"]
            or before_tree["unsafe_entry_detected"]
            or before_tree["scan_error"]
        ):
            raise ContractError("执行前 workspace 已超出配额")
        plan_record = {
            "schema_version": "case11_container_creation_record_v2",
            "creation_record_id": args.invocation_id,
            "status": "approved_not_created",
            "attempt_id": args.attempt_id,
            "invocation_id": args.invocation_id,
            "container_name": container_name,
            "host_alias": plan["labels"]["agent_sft.host_alias"],
            "purpose": "case11_sandbox_validation",
            "planned_at": utc_now(),
        }
        update_resource_manifest(resource_manifest, "plan", plan_record)
        creation_planned = True
        created = run_bytes(expected_create_args(contract, plan, attempt_dir, args.attempt_id, container_name), timeout=30)
        if created.returncode != 0:
            update_resource_manifest(
                resource_manifest,
                "failed",
                {"creation_record_id": args.invocation_id, "status": "create_failed", "failed_at": utc_now(), "error_code": "docker_create_nonzero"},
            )
            raise ContractError("docker create 失败：" + tail_text(created.stderr, 180))
        container_id = created.stdout.decode("ascii", errors="strict").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", container_id):
            update_resource_manifest(
                resource_manifest,
                "failed",
                {"creation_record_id": args.invocation_id, "status": "create_failed", "failed_at": utc_now(), "error_code": "invalid_container_id"},
            )
            raise ContractError("容器 ID 无效")
        update_resource_manifest(
            resource_manifest,
            "created",
            {
                "creation_record_id": args.invocation_id,
                "status": "created",
                "container_id": container_id,
                "container_name": container_name,
                "attempt_id": args.attempt_id,
                "invocation_id": args.invocation_id,
                "created_at": utc_now(),
            },
        )
        pre = docker_json(container_id)
        pre_errors = inspect_contract(pre, contract, plan, attempt_dir, args.attempt_id, require_stopped=False)
        append_record(
            evidence_root / "container_records.jsonl",
            {
                "schema_version": RECORD_SCHEMA,
                "container_id": container_id,
                "container_name": container_name,
                "attempt_id": args.attempt_id,
                "invocation_id": args.invocation_id,
                "recorded_at": utc_now(),
                "preflight_contract_errors": pre_errors,
            },
        )
        if pre_errors:
            raise ContractError("pre-start inspect 不满足合同：" + ",".join(pre_errors))
        started = run_bytes(["docker", "start", container_id], timeout=15)
        if started.returncode != 0:
            raise ContractError("docker start 失败：" + tail_text(started.stderr, 180))
        started_container = True
        deadline = time.monotonic() + int(contract["wall_time_seconds"])
        while True:
            inspected = docker_json(container_id)
            state = inspected.get("State", {})
            usage = bounded_inventory(
                attempt_dir,
                contract,
                hash_regular=False,
                tolerate_disappeared=True,
            )
            if usage["byte_limit_exceeded"]:
                quota_exceeded = True
            if usage["entry_limit_exceeded"]:
                entry_limit_exceeded = True
            if usage["single_file_limit_exceeded"]:
                single_file_limit_exceeded = True
            if usage["unsafe_entry_detected"]:
                unsafe_entry_detected = True
            if usage["scan_error"]:
                inventory_scan_failed = True
            if (
                quota_exceeded
                or entry_limit_exceeded
                or single_file_limit_exceeded
                or unsafe_entry_detected
                or inventory_scan_failed
            ):
                run_bytes(["docker", "kill", container_id], timeout=10)
                break
            if state.get("Running") is False:
                candidate_exit = state.get("ExitCode") if isinstance(state.get("ExitCode"), int) else None
                break
            if time.monotonic() >= deadline:
                timed_out = True
                run_bytes(["docker", "kill", container_id], timeout=10)
                break
            time.sleep(0.02)
        final_inspect = force_quiescent(container_id)
        if final_inspect is None:
            raise ContractError("无法取得容器终态")
        state = final_inspect.get("State", {})
        candidate_exit = state.get("ExitCode") if isinstance(state.get("ExitCode"), int) else candidate_exit
        post_errors = inspect_contract(final_inspect, contract, plan, attempt_dir, args.attempt_id, require_stopped=True)
        diff = run_bytes(["docker", "diff", container_id], timeout=10)
        diff_lines = sorted(line for line in diff.stdout.decode("utf-8", errors="replace").splitlines() if line)
        if diff.returncode != 0 or diff_lines != sorted(contract["allowed_docker_diff"]):
            post_errors.append("docker_diff")
        after_tree = bounded_inventory(
            attempt_dir,
            contract,
            hash_regular=True,
            tolerate_disappeared=False,
        )
        quota_exceeded = quota_exceeded or bool(after_tree["byte_limit_exceeded"])
        entry_limit_exceeded = entry_limit_exceeded or bool(after_tree["entry_limit_exceeded"])
        single_file_limit_exceeded = single_file_limit_exceeded or bool(after_tree["single_file_limit_exceeded"])
        unsafe_entry_detected = unsafe_entry_detected or bool(after_tree["unsafe_entry_detected"])
        inventory_scan_failed = inventory_scan_failed or bool(after_tree["scan_error"])
    except (ContractError, OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.SubprocessError, UnicodeError) as exc:
        controller_error = f"{type(exc).__name__}:{str(exc)[:300]}"
    finally:
        if container_id:
            final_inspect = force_quiescent(container_id)
            if final_inspect is not None and contract and plan and attempt_dir is not None:
                final_post = inspect_contract(final_inspect, contract, plan, attempt_dir, args.attempt_id, require_stopped=True)
                post_errors = sorted(set(post_errors + final_post))
                state = final_inspect.get("State", {})
                if isinstance(state.get("ExitCode"), int):
                    candidate_exit = state["ExitCode"]
        if attempt_dir is not None and contract:
            try:
                after_tree = bounded_inventory(
                    attempt_dir,
                    contract,
                    hash_regular=True,
                    tolerate_disappeared=False,
                )
                quota_exceeded = quota_exceeded or bool(after_tree["byte_limit_exceeded"])
                entry_limit_exceeded = entry_limit_exceeded or bool(after_tree["entry_limit_exceeded"])
                single_file_limit_exceeded = single_file_limit_exceeded or bool(after_tree["single_file_limit_exceeded"])
                unsafe_entry_detected = unsafe_entry_detected or bool(after_tree["unsafe_entry_detected"])
                inventory_scan_failed = inventory_scan_failed or bool(after_tree["scan_error"])
            except OSError:
                post_errors.append("post_inventory")
        stdout_tail = ""
        stderr_tail = ""
        if container_id and contract:
            try:
                logs = run_bytes(["docker", "logs", "--tail", "512", container_id], timeout=10)
                limit = int(contract["max_captured_log_bytes"])
                log_limit_exceeded = len(logs.stdout) + len(logs.stderr) > limit
                stdout_tail = tail_text(logs.stdout, limit)
                stderr_tail = tail_text(logs.stderr, limit)
            except subprocess.SubprocessError:
                post_errors.append("bounded_logs")
        controller_status = (
            "passed"
            if not controller_error
            and not pre_errors
            and not post_errors
            and not quota_exceeded
            and not entry_limit_exceeded
            and not single_file_limit_exceeded
            and not unsafe_entry_detected
            and not log_limit_exceeded
            and not inventory_scan_failed
            else "failed"
        )
        result = {
            "schema_version": RESULT_SCHEMA,
            "controller_status": controller_status,
            "attempt_id": args.attempt_id,
            "invocation_id": args.invocation_id,
            "container_id": container_id or None,
            "container_name": container_name or None,
            "creation_predeclared": creation_planned,
            "candidate_exit_code": candidate_exit,
            "timed_out": timed_out,
            "quota_exceeded": quota_exceeded,
            "entry_limit_exceeded": entry_limit_exceeded,
            "single_file_limit_exceeded": single_file_limit_exceeded,
            "unsafe_entry_detected": unsafe_entry_detected,
            "log_limit_exceeded": log_limit_exceeded,
            "inventory_scan_failed": inventory_scan_failed,
            "started_container": started_container,
            "preflight_contract_errors": pre_errors,
            "postflight_contract_errors": sorted(set(post_errors)),
            "controller_error": controller_error or None,
            "duration_seconds": round(time.monotonic() - started_at, 6),
            "before_inventory": before_tree,
            "after_inventory": after_tree,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }
        if result_path is not None and not result_path.exists():
            try:
                atomic_json(result_path, result)
            except (OSError, ContractError):
                pass
        sys.stdout.write(json.dumps({"status": controller_status, "container_id": container_id or None}, sort_keys=True) + "\n")
        return 0 if controller_status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
