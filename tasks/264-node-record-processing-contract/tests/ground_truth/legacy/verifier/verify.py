#!/usr/bin/env python3
"""Deterministic, bounded verifier for case_10.

The trusted controller never imports or executes candidate JavaScript in its own
process.  Candidate bytes are admitted through a bounded tree scan, copied into
an exact managed bind source, and executed only in the separately confined
candidate container named by the v2 ownership plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import selectors
import shutil
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = CASE_ROOT / "fixtures" / "initial_repo"
CONTRACT_PATH = CASE_ROOT / "environment" / "candidate_sandbox_contract.json"
HIDDEN_CASES_PATH = CASE_ROOT / "tests" / "hidden_cases.json"
CONTROLLER_ROOT = Path("/runtime")
CANDIDATES_ROOT = CONTROLLER_ROOT / "candidates"
MAX_DOCKER_CONTROL_BYTES = 2 * 1024 * 1024
EXACT_ID_RE = re.compile(r"^[a-f0-9]{64}$")
SECRET_NAME_RE = re.compile(
    r"(?:SECRET|TOKEN|API_KEY|PASSWORD|CREDENTIAL|AUTHORIZATION|PROXY)", re.I
)


class VerificationError(RuntimeError):
    """Infrastructure or ownership failure that makes an attempt invalid."""


class CandidateJSONError(ValueError):
    """Malformed or ambiguous candidate JSON that must be rejected."""


def load_candidate_json(raw: bytes) -> Any:
    """Parse bounded candidate JSON while rejecting duplicate keys/constants."""

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for key, value in pairs:
            if key in parsed:
                raise CandidateJSONError("duplicate JSON object key")
            parsed[key] = value
        return parsed

    def reject_constant(value: str) -> None:
        raise CandidateJSONError(f"non-standard JSON constant: {value}")

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_constant,
    )


def strict_json_equal(observed: Any, expected: Any) -> bool:
    """Compare JSON values without Python's bool/int equality coercion."""

    if isinstance(observed, bool) or isinstance(expected, bool):
        return isinstance(observed, bool) and isinstance(expected, bool) and observed == expected
    if isinstance(observed, (int, float)) and isinstance(expected, (int, float)):
        return (
            not isinstance(observed, bool)
            and not isinstance(expected, bool)
            and (not isinstance(observed, float) or math.isfinite(observed))
            and (not isinstance(expected, float) or math.isfinite(expected))
            and observed == expected
        )
    if type(observed) is not type(expected):
        return False
    if isinstance(observed, dict):
        return set(observed) == set(expected) and all(
            strict_json_equal(observed[key], expected[key]) for key in observed
        )
    if isinstance(observed, list):
        return len(observed) == len(expected) and all(
            strict_json_equal(left, right)
            for left, right in zip(observed, expected, strict=True)
        )
    return observed == expected


def canonical_json_sha256(
    value: Any, excluded_keys: set[str] | None = None
) -> str:
    if isinstance(value, dict) and excluded_keys:
        value = {key: item for key, item in value.items() if key not in excluded_keys}
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    return os.path.commonpath([str(path.absolute()), str(root.absolute())]) == str(
        root.absolute()
    )


def _check_real_child(root: Path, allowed_root: Path) -> str | None:
    root = root.absolute()
    allowed_root = allowed_root.absolute()
    if root == allowed_root or not _inside(root, allowed_root):
        return "path_outside_managed_root"
    current = allowed_root
    try:
        if not stat.S_ISDIR(os.lstat(allowed_root).st_mode):
            return "managed_root_not_directory"
        for part in root.relative_to(allowed_root).parts:
            current = current / part
            mode = os.lstat(current).st_mode
            if stat.S_ISLNK(mode):
                return "symlink_in_managed_path"
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            return "source_not_directory"
    except OSError:
        return "source_path_unreadable"
    return None


def bounded_tree_scan(
    root: Path,
    *,
    allowed_root: Path,
    max_entries: int,
    max_total_bytes: int,
    max_file_bytes: int,
    max_depth: int,
    max_relative_path_bytes: int,
) -> dict[str, Any]:
    """Scan at most ``max_entries + 1`` entries and read only admitted bytes."""

    reason = _check_real_child(root, allowed_root)
    descriptors: list[dict[str, Any]] = []
    total_bytes = 0
    stack: list[tuple[Path, str, int]] = []
    if reason is None:
        stack.append((root.absolute(), "", 0))
    while stack and reason is None:
        directory, prefix, parent_depth = stack.pop()
        try:
            iterator = os.scandir(directory)
        except OSError:
            reason = "directory_unreadable"
            break
        with iterator:
            for entry in iterator:
                relative = f"{prefix}/{entry.name}" if prefix else entry.name
                depth = parent_depth + 1
                if len(descriptors) >= max_entries:
                    reason = "entry_limit_exceeded"
                    descriptors.append({"path": relative, "type": "limit_marker"})
                    break
                if len(relative.encode("utf-8", errors="surrogatepass")) > max_relative_path_bytes:
                    reason = "relative_path_limit_exceeded"
                    descriptors.append({"path": relative, "type": "path_limit_marker"})
                    break
                if depth > max_depth:
                    reason = "depth_limit_exceeded"
                    descriptors.append({"path": relative, "type": "depth_limit_marker"})
                    break
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except OSError:
                    reason = "entry_stat_failed"
                    descriptors.append({"path": relative, "type": "stat_error"})
                    break
                mode = metadata.st_mode
                if stat.S_ISLNK(mode):
                    reason = "symlink_forbidden"
                    descriptors.append({"path": relative, "type": "symlink"})
                    break
                if stat.S_ISDIR(mode):
                    descriptors.append({"path": relative, "type": "directory"})
                    stack.append((Path(entry.path), relative, depth))
                    continue
                if not stat.S_ISREG(mode):
                    reason = "non_regular_entry_forbidden"
                    descriptors.append({"path": relative, "type": "other"})
                    break
                descriptor: dict[str, Any] = {
                    "path": relative,
                    "type": "file",
                    "size": metadata.st_size,
                }
                descriptors.append(descriptor)
                if metadata.st_nlink != 1:
                    reason = "hardlink_forbidden"
                    break
                if metadata.st_size > max_file_bytes:
                    reason = "single_file_limit_exceeded"
                    break
                total_bytes += metadata.st_size
                if total_bytes > max_total_bytes:
                    reason = "total_byte_limit_exceeded"
                    break
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                try:
                    descriptor_fd = os.open(entry.path, flags)
                    with os.fdopen(descriptor_fd, "rb") as handle:
                        opened = os.fstat(handle.fileno())
                        if (
                            not stat.S_ISREG(opened.st_mode)
                            or opened.st_nlink != 1
                            or opened.st_size != metadata.st_size
                            or opened.st_ino != metadata.st_ino
                            or opened.st_dev != metadata.st_dev
                        ):
                            reason = "source_changed_during_scan"
                            break
                        digest = hashlib.sha256()
                        observed = 0
                        for chunk in iter(lambda: handle.read(65536), b""):
                            observed += len(chunk)
                            if observed > max_file_bytes:
                                reason = "single_file_limit_exceeded"
                                break
                            digest.update(chunk)
                        if reason is not None:
                            break
                        if observed != metadata.st_size:
                            reason = "source_changed_during_scan"
                            break
                        descriptor["sha256"] = digest.hexdigest()
                except OSError:
                    reason = "file_read_failed"
                    break
    canonical = {
        "entries": sorted(descriptors, key=lambda item: (item["path"], item["type"])),
        "reason": reason,
        "total_bytes": total_bytes,
    }
    return {
        "safe": reason is None,
        "reason": reason,
        "entry_count": len(descriptors),
        "file_count": sum(item["type"] == "file" for item in descriptors),
        "directory_count": sum(item["type"] == "directory" for item in descriptors),
        "total_bytes": total_bytes,
        "entries": canonical["entries"],
        "tree_sha256": canonical_json_sha256(canonical),
    }


def scan_tree_for_contract(
    root: Path, allowed_root: Path, contract: dict[str, Any]
) -> dict[str, Any]:
    filesystem = contract["filesystem"]
    return bounded_tree_scan(
        root,
        allowed_root=allowed_root,
        max_entries=filesystem["max_submission_entries"],
        max_total_bytes=filesystem["max_submission_bytes"],
        max_file_bytes=filesystem["max_single_source_file_bytes"],
        max_depth=filesystem["max_submission_depth"],
        max_relative_path_bytes=filesystem["max_relative_path_bytes"],
    )


def inventory_shape(scan: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["path"], item["type"]) for item in scan["entries"]]


def entry_hashes(scan: dict[str, Any]) -> dict[str, str]:
    return {
        item["path"]: item["sha256"]
        for item in scan["entries"]
        if item["type"] == "file" and "sha256" in item
    }


def run_bounded(
    command: list[str],
    *,
    input_bytes: bytes = b"",
    timeout_seconds: float,
    stdout_limit: int,
    stderr_limit: int,
) -> dict[str, Any]:
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    def write_input() -> None:
        try:
            if input_bytes:
                process.stdin.write(input_bytes)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    writer = threading.Thread(target=write_input, daemon=True)
    writer.start()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    overflow_stream: str | None = None
    timed_out = False
    deadline = started + timeout_seconds
    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        events = selector.select(min(0.1, remaining))
        if not events and process.poll() is not None:
            events = [(key, selectors.EVENT_READ) for key in selector.get_map().values()]
        for key, _ in events:
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            name = key.data
            buffers[name].extend(chunk)
            limit = stdout_limit if name == "stdout" else stderr_limit
            if len(buffers[name]) > limit:
                overflow_stream = name
                break
        if overflow_stream:
            break
    if timed_out or overflow_stream:
        process.kill()
    try:
        return_code = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        return_code = process.wait(timeout=2)
    writer.join(timeout=0.2)
    return {
        "return_code": return_code,
        "stdout": bytes(buffers["stdout"][:stdout_limit]),
        "stderr": bytes(buffers["stderr"][:stderr_limit]),
        "stdout_bytes": len(buffers["stdout"]),
        "stderr_bytes": len(buffers["stderr"]),
        "overflow_stream": overflow_stream,
        "timed_out": timed_out,
        "duration_seconds": time.monotonic() - started,
    }


def docker_control(
    args: list[str], timeout: float = 20
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["/usr/bin/docker", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if (
        len(completed.stdout) > MAX_DOCKER_CONTROL_BYTES
        or len(completed.stderr) > MAX_DOCKER_CONTROL_BYTES
    ):
        raise VerificationError("bounded Docker control output exceeded")
    return completed


def require_docker_ok(args: list[str], timeout: float = 20) -> bytes:
    completed = docker_control(args, timeout)
    if completed.returncode != 0:
        stderr_hash = hashlib.sha256(completed.stderr).hexdigest()
        raise VerificationError(
            f"Docker command failed ({args[0]}), stderr_sha256={stderr_hash}"
        )
    return completed.stdout


def load_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = canonical_json_sha256(contract, {"contract_sha256"})
    if contract.get("contract_sha256") != expected:
        raise VerificationError("candidate sandbox contract canonical hash mismatch")
    if contract.get("schema_version") != "nami_work_candidate_sandbox_contract_v2":
        raise VerificationError("candidate sandbox contract schema mismatch")
    return contract


def load_plan(path: Path, contract: dict[str, Any]) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "case_id",
        "run_id",
        "task_id",
        "host_alias",
        "hostname",
        "attempt_id",
        "host_runtime_root",
        "controller_runtime_root",
        "submission_relative_path",
        "contract_sha256",
        "resource_manifest_path",
        "candidate_container",
        "controller_container",
        "dynamic_labels",
    }
    if not required.issubset(plan):
        raise VerificationError("ownership plan is incomplete")
    if (
        plan["case_id"] != "case_10"
        or plan["schema_version"] != "nami_work_candidate_runtime_ownership_v2"
    ):
        raise VerificationError("ownership plan case/schema mismatch")
    if plan["contract_sha256"] != contract["contract_sha256"]:
        raise VerificationError("ownership plan contract hash mismatch")
    if plan["controller_runtime_root"] != "/runtime":
        raise VerificationError("controller runtime root mismatch")
    if plan["submission_relative_path"] != "submission":
        raise VerificationError("submission relative path mismatch")
    if not isinstance(plan["resource_manifest_path"], str) or not plan[
        "resource_manifest_path"
    ].startswith("artifacts/resource_governance/"):
        raise VerificationError("resource manifest path is absent or invalid")
    for role in ("candidate_container", "controller_container"):
        exact_id = plan[role].get("exact_id")
        if not isinstance(exact_id, str) or not EXACT_ID_RE.fullmatch(exact_id):
            raise VerificationError(f"{role} exact ID is absent or malformed")
    return plan


def parse_env_names(env_entries: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for entry in env_entries:
        key, separator, value = entry.partition("=")
        if not separator or not key or key in parsed:
            raise VerificationError("malformed or duplicate container environment entry")
        parsed[key] = value
    return parsed


def inspect_json(exact_id: str) -> dict[str, Any]:
    raw = require_docker_ok(["inspect", exact_id])
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise VerificationError("unexpected Docker inspect shape")
    if parsed[0].get("Id") != exact_id:
        raise VerificationError("Docker inspect exact ID mismatch")
    return parsed[0]


def inspect_owned(
    plan: dict[str, Any], contract: dict[str, Any], *, require_running: bool
) -> dict[str, Any]:
    exact_id = plan["candidate_container"]["exact_id"]
    inspected = inspect_json(exact_id)
    failures: list[str] = []
    if inspected.get("Name") != f"/{plan['candidate_container']['name']}":
        failures.append("name")
    labels = inspected.get("Config", {}).get("Labels") or {}
    for key, value in plan["dynamic_labels"].items():
        if labels.get(key) != value:
            failures.append(f"label:{key}")
    if labels.get("agent_sft.runtime_role") != contract["runtime_role"]:
        failures.append("label:runtime_role")
    if labels.get("agent_sft.sandbox_contract_sha256") != contract["contract_sha256"]:
        failures.append("label:contract_sha256")
    if labels.get("agent_sft.resource_manifest_path") != plan["resource_manifest_path"]:
        failures.append("label:resource_manifest_path")
    host_config = inspected.get("HostConfig", {})
    config = inspected.get("Config", {})
    state = inspected.get("State", {})
    if inspected.get("Image") != contract["image"]["digest"]:
        failures.append("image_digest")
    if host_config.get("NetworkMode") != contract["network"]["mode"]:
        failures.append("network")
    if host_config.get("PortBindings") not in (None, {}):
        failures.append("published_ports")
    if config.get("ExposedPorts") not in (None, {}):
        failures.append("exposed_ports")
    if config.get("User") != contract["identity"]["user"]:
        failures.append("user")
    if host_config.get("Privileged") is not False:
        failures.append("privileged")
    if host_config.get("AutoRemove") is not False:
        failures.append("auto_remove")
    if (host_config.get("RestartPolicy") or {}).get("Name") != contract["security"][
        "restart_policy"
    ]:
        failures.append("restart_policy")
    if not host_config.get("ReadonlyRootfs"):
        failures.append("readonly_rootfs")
    if set(host_config.get("CapDrop") or []) != set(contract["security"]["cap_drop"]):
        failures.append("cap_drop")
    if host_config.get("CapAdd") not in (None, []):
        failures.append("cap_add")
    if "no-new-privileges" not in (host_config.get("SecurityOpt") or []):
        failures.append("no_new_privileges")
    if host_config.get("IpcMode") != contract["security"]["ipc_mode"]:
        failures.append("ipc_mode")
    for docker_key, contract_key in (
        ("PidMode", "pid_mode"),
        ("UTSMode", "uts_mode"),
        ("UsernsMode", "userns_mode"),
    ):
        if (host_config.get(docker_key) or "") != contract["security"][contract_key]:
            failures.append(contract_key)
    if host_config.get("Devices") not in (None, []):
        failures.append("devices")
    if host_config.get("GroupAdd") not in (None, []):
        failures.append("supplementary_groups")
    resources = contract["resources"]
    if host_config.get("NanoCpus") != resources["cpu_cores"] * 1_000_000_000:
        failures.append("cpu_limit")
    if host_config.get("Memory") != resources["memory_bytes"]:
        failures.append("memory_limit")
    if host_config.get("MemorySwap") != resources["memory_swap_bytes"]:
        failures.append("memory_swap_limit")
    if host_config.get("PidsLimit") != resources["pids_limit"]:
        failures.append("pids_limit")
    if host_config.get("ShmSize") != contract["filesystem"]["shm"]["max_bytes"]:
        failures.append("shm_size")
    ulimits = {
        item["Name"]: (item["Soft"], item["Hard"])
        for item in host_config.get("Ulimits") or []
    }
    if ulimits.get("fsize") != (resources["fsize_bytes"], resources["fsize_bytes"]):
        failures.append("fsize_limit")
    if ulimits.get("nofile") != (resources["nofile"], resources["nofile"]):
        failures.append("nofile_limit")
    if config.get("WorkingDir") != contract["filesystem"]["working_directory"]:
        failures.append("working_directory")
    if config.get("Entrypoint") != contract["process"]["entrypoint"]:
        failures.append("entrypoint")
    if config.get("Cmd") != contract["process"]["command"]:
        failures.append("command")
    mounts = inspected.get("Mounts") or []
    expected_mounts = {
        item["destination"]: {
            "source": f"{plan['host_runtime_root']}/{item['source_relative_to_host_runtime_root']}",
            "readonly": item["readonly"],
        }
        for item in contract["filesystem"]["mounts"]
    }
    observed_mounts = {item.get("Destination"): item for item in mounts}
    if set(observed_mounts) != set(expected_mounts):
        failures.append("mount_count")
    else:
        for destination, expected_mount in expected_mounts.items():
            observed_mount = observed_mounts[destination]
            if not (
                observed_mount.get("Type") == "bind"
                and observed_mount.get("Source") == expected_mount["source"]
                and observed_mount.get("RW") == (not expected_mount["readonly"])
            ):
                failures.append(f"mount:{destination}")
    tmpfs = host_config.get("Tmpfs") or {}
    expected_tmpfs = contract["filesystem"]["tmpfs"]
    if set(tmpfs) != set(expected_tmpfs):
        failures.append("tmpfs_mounts")
    for destination, expected in expected_tmpfs.items():
        options = set((tmpfs.get(destination) or "").split(","))
        if not set(expected["options"]).issubset(options):
            failures.append(f"tmpfs_options:{destination}")
    env = parse_env_names(config.get("Env") or [])
    allowed_names = set(contract["security"]["allowed_config_environment_names"])
    if not set(env).issubset(allowed_names):
        failures.append("environment_name_allowlist")
    for key, expected in contract["security"]["required_config_environment"].items():
        if env.get(key) != expected:
            failures.append(f"environment:{key}")
    if any(SECRET_NAME_RE.search(key) and value for key, value in env.items()):
        failures.append("nonempty_credential_environment")
    if require_running and not (
        state.get("Running") is True and isinstance(state.get("Pid"), int) and state["Pid"] > 0
    ):
        failures.append("container_not_running")
    submission = CONTROLLER_ROOT / plan["submission_relative_path"]
    path_reason = _check_real_child(submission, CONTROLLER_ROOT)
    if path_reason is not None:
        failures.append(f"managed_submission:{path_reason}")
    if failures:
        raise VerificationError(
            f"candidate ownership/config mismatch: {','.join(sorted(failures))}"
        )
    return inspected


def container_state(exact_id: str) -> dict[str, Any]:
    inspected = inspect_json(exact_id)
    state = inspected.get("State", {})
    return {
        "running": state.get("Running") is True,
        "pid": state.get("Pid") if isinstance(state.get("Pid"), int) else -1,
        "status": str(state.get("Status", "unknown")),
        "exit_code": state.get("ExitCode") if isinstance(state.get("ExitCode"), int) else -1,
        "oom_killed": state.get("OOMKilled") is True,
    }


def clear_and_copy_source(
    source: Path,
    submission: Path,
    source_scan: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    if _check_real_child(submission, CONTROLLER_ROOT) is not None:
        raise VerificationError("submission target is not a real managed directory")
    for child in submission.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
        else:
            raise VerificationError("unsupported existing submission entry")
    directories = [
        item["path"] for item in source_scan["entries"] if item["type"] == "directory"
    ]
    files = [item["path"] for item in source_scan["entries"] if item["type"] == "file"]
    for relative in sorted(directories, key=lambda item: (item.count("/"), item)):
        destination = submission / relative
        destination.mkdir(mode=0o755)
    for relative in sorted(files):
        destination = submission / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, destination, follow_symlinks=False)
        destination.chmod(0o644)
    copied_scan = scan_tree_for_contract(submission, CONTROLLER_ROOT, contract)
    if (
        not copied_scan["safe"]
        or copied_scan["tree_sha256"] != source_scan["tree_sha256"]
        or inventory_shape(copied_scan) != inventory_shape(source_scan)
        or entry_hashes(copied_scan) != entry_hashes(source_scan)
    ):
        raise VerificationError("bounded submission copy verification failed")
    return copied_scan


def validate_submission_static(
    source_scan: dict[str, Any], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    fixture_scan = scan_tree_for_contract(FIXTURE_ROOT, CASE_ROOT / "fixtures", contract)
    if not fixture_scan["safe"]:
        raise VerificationError("trusted fixture violates candidate tree contract")
    candidate_shape = inventory_shape(source_scan)
    fixture_shape = inventory_shape(fixture_scan)
    exact_inventory = candidate_shape == fixture_shape
    checks: list[dict[str, Any]] = [
        {
            "check_id": "submission_exact_inventory",
            "passed": exact_inventory,
            "evidence": {
                "entry_count": source_scan["entry_count"],
                "expected_entry_count": fixture_scan["entry_count"],
                "inventory_sha256": canonical_json_sha256(candidate_shape),
            },
        },
        {
            "check_id": "submission_size_bounds",
            "passed": source_scan["safe"],
            "evidence": {
                "total_bytes": source_scan["total_bytes"],
                "max_total_bytes": contract["filesystem"]["max_submission_bytes"],
            },
        },
    ]
    fixture_hashes = entry_hashes(fixture_scan)
    candidate_hashes = entry_hashes(source_scan)
    protected = set(fixture_hashes) - {"src/process.js"}
    changed = sorted(
        relative
        for relative in protected
        if candidate_hashes.get(relative) != fixture_hashes[relative]
    )
    checks.append(
        {
            "check_id": "protected_files_unchanged",
            "passed": exact_inventory and not changed,
            "evidence": {
                "changed_count": len(changed),
                "changed_paths_sha256": hashlib.sha256("\n".join(changed).encode()).hexdigest(),
            },
        }
    )
    package_path = FIXTURE_ROOT / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    no_dependencies = not any(
        package.get(key)
        for key in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        )
    )
    checks.append(
        {
            "check_id": "no_network_dependencies",
            "passed": bool(no_dependencies and candidate_hashes.get("package.json") == file_sha256(package_path)),
            "evidence": {
                "dependency_sections_nonempty": sum(
                    bool(package.get(key))
                    for key in (
                        "dependencies",
                        "devDependencies",
                        "optionalDependencies",
                        "peerDependencies",
                    )
                )
            },
        }
    )
    return checks


def process_count(exact_id: str) -> int:
    output = require_docker_ok(["top", exact_id, "-eo", "pid,ppid,comm,args"])
    lines = [
        line
        for line in output.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    return max(0, len(lines) - 1)


def runtime_roots_state(exact_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    roots = {
        item["path"]: item["expected_mode"]
        for item in contract["filesystem"]["runtime_roots"]
    }
    limit = contract["filesystem"]["max_runtime_entries_per_root"]
    script = r'''
import hashlib, json, os, stat, sys
roots = json.loads(sys.argv[1])
limit = int(sys.argv[2])
result = {}
for root, expected_mode in roots.items():
    names = []
    overflow = False
    stack = [(root, "", 0)]
    error = None
    try:
        mode = format(stat.S_IMODE(os.lstat(root).st_mode), "04o")
        if mode != expected_mode:
            result[root] = {
                "mode": mode,
                "expected_mode": expected_mode,
                "entry_count": 0,
                "overflow": False,
                "entry_names_sha256": hashlib.sha256(b"").hexdigest(),
                "error": None,
            }
            continue
        while stack and not overflow:
            directory, prefix, depth = stack.pop()
            if depth >= 8:
                continue
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    relative = f"{prefix}/{entry.name}" if prefix else entry.name
                    names.append(relative)
                    if len(names) > limit:
                        overflow = True
                        break
                    metadata = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                        stack.append((entry.path, relative, depth + 1))
    except Exception as exc:
        mode = "error"
        error = type(exc).__name__
    result[root] = {
        "mode": mode,
        "expected_mode": expected_mode,
        "entry_count": len(names),
        "overflow": overflow,
        "entry_names_sha256": hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest(),
        "error": error,
    }
sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
'''
    completed = docker_control(
        [
            "exec",
            "--user",
            "65534:65534",
            "--workdir",
            "/",
            exact_id,
            "python3",
            "-c",
            script,
            json.dumps(roots, sort_keys=True),
            str(limit),
        ],
        10,
    )
    if completed.returncode != 0 or len(completed.stdout) > 4096:
        raise VerificationError("bounded runtime-root probe failed")
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("runtime-root probe returned malformed JSON") from error
    clean = all(
        item.get("mode") == item.get("expected_mode")
        and item.get("entry_count") == 0
        and item.get("overflow") is False
        and item.get("error") is None
        for item in parsed.values()
    )
    return {"roots": parsed, "clean": clean}


def boundary_probe(exact_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    paths = contract["security"]["forbidden_visible_paths"]
    script = (
        "const fs=require('node:fs');"
        f"const p={json.dumps(paths)};"
        "const visible=p.filter(x=>fs.existsSync(x)).length;"
        "const r=/(SECRET|TOKEN|API_KEY|PASSWORD|CREDENTIAL|AUTHORIZATION|PROXY)/i;"
        "const env=Object.entries(process.env).filter(([k,v])=>v&&r.test(k)).length;"
        "process.stdout.write(JSON.stringify({visible,env}));"
    )
    completed = docker_control(
        ["exec", "--user", "0:0", exact_id, "node", "-e", script], 10
    )
    if completed.returncode != 0 or len(completed.stdout) > 256:
        raise VerificationError("candidate boundary probe failed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError("candidate boundary probe returned malformed JSON") from error
    return {
        "forbidden_visible_path_count": result["visible"],
        "forbidden_nonempty_env_count": result["env"],
    }


def ensure_clean_rest(exact_id: str, contract: dict[str, Any]) -> dict[str, Any]:
    state = container_state(exact_id)
    if not state["running"] or state["pid"] <= 0:
        raise VerificationError("candidate failed to run after trusted restart")
    runtime = runtime_roots_state(exact_id, contract)
    count = process_count(exact_id)
    boundary = boundary_probe(exact_id, contract)
    clean = (
        runtime["clean"]
        and count == contract["process"]["expected_process_count_at_rest"]
        and boundary["forbidden_visible_path_count"] == 0
        and boundary["forbidden_nonempty_env_count"] == 0
    )
    return {
        "container": state,
        "runtime_roots": runtime,
        "process_count": count,
        **boundary,
        "clean": clean,
    }


def codepoint_key(value: str) -> tuple[int, ...]:
    return tuple(ord(character) for character in value)


def normalize_expected(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(payload["records"]):
        cents = round(record["amount"] * 100)
        normalized.append(
            {
                "id": record["id"].strip(),
                "category": record["category"].strip(),
                "amount": cents / 100,
                "priority": record.get("priority", 0),
                "active": record.get("active", True),
                "_cents": cents,
                "_index": index,
            }
        )
    ordered = sorted(
        normalized,
        key=lambda item: (
            codepoint_key(item["category"]),
            -item["_cents"],
            -item["priority"],
            item["_index"],
        ),
    )
    categories: dict[str, dict[str, int]] = {}
    for item in normalized:
        bucket = categories.setdefault(
            item["category"], {"count": 0, "active": 0, "cents": 0}
        )
        bucket["count"] += 1
        bucket["active"] += int(item["active"])
        bucket["cents"] += item["_cents"]
    records = [
        {key: item[key] for key in ("id", "category", "amount", "priority", "active")}
        for item in ordered
    ]
    by_category = [
        {
            "category": category,
            "count": categories[category]["count"],
            "activeCount": categories[category]["active"],
            "totalAmount": categories[category]["cents"] / 100,
        }
        for category in sorted(categories, key=codepoint_key)
    ]
    return {
        "records": records,
        "summary": {
            "inputCount": len(records),
            "activeCount": sum(int(item["active"]) for item in normalized),
            "totalAmount": sum(item["_cents"] for item in normalized) / 100,
            "byCategory": by_category,
        },
    }


def performance_payload(spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("generator") == "compact_max_records":
        return {
            "records": [
                {"id": str(index), "category": "x", "amount": 0}
                for index in range(spec["record_count"])
            ]
        }
    records = []
    for index in range(spec["record_count"]):
        records.append(
            {
                "id": f"perf-{index:05d}",
                "category": f"category-{index % spec['category_count']:02d}",
                "amount": (index * 7919 % spec["amount_modulus_cents"]) / 100,
                "priority": index % 17 - 8,
                "active": index % 5 != 0,
            }
        )
    return {"records": records}


def candidate_invocation(
    exact_id: str, raw_input: bytes, contract: dict[str, Any], timeout: float
) -> dict[str, Any]:
    return run_bounded(
        [
            "/usr/bin/docker",
            "exec",
            "-i",
            exact_id,
            *contract["process"]["candidate_command"],
        ],
        input_bytes=raw_input,
        timeout_seconds=timeout,
        stdout_limit=contract["filesystem"]["max_stdout_bytes"],
        stderr_limit=contract["filesystem"]["max_stderr_bytes"],
    )


def result_evidence(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_code": result["return_code"],
        "duration_seconds": round(result["duration_seconds"], 6),
        "stdout_bytes": result["stdout_bytes"],
        "stderr_bytes": result["stderr_bytes"],
        "stdout_sha256": hashlib.sha256(result["stdout"]).hexdigest(),
        "stderr_sha256": hashlib.sha256(result["stderr"]).hexdigest(),
        "timed_out": result["timed_out"],
        "overflow_stream": result["overflow_stream"],
    }


def post_invocation_guard(
    exact_id: str, contract: dict[str, Any]
) -> tuple[bool, dict[str, Any], str | None]:
    state = container_state(exact_id)
    if not state["running"]:
        return False, {"container": state}, "candidate_container_stopped"
    runtime = runtime_roots_state(exact_id, contract)
    count = process_count(exact_id)
    evidence = {"container": state, "runtime_roots": runtime, "process_count": count}
    if not runtime["clean"]:
        return False, evidence, "candidate_runtime_side_effect"
    if count != contract["process"]["expected_process_count_at_rest"]:
        return False, evidence, "candidate_process_leak"
    return True, evidence, None


def run_functional_suite(
    exact_id: str, contract: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hidden = json.loads(HIDDEN_CASES_PATH.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    durations: list[float] = []
    stdout_sizes: list[int] = []
    stderr_sizes: list[int] = []

    def current_metrics(aborted_reason: str | None = None) -> dict[str, Any]:
        return {
            "attempt_count": len(durations),
            "max_duration_seconds": max(durations, default=0),
            "max_stdout_bytes": max(stdout_sizes, default=0),
            "max_stderr_bytes": max(stderr_sizes, default=0),
            "execution_aborted": aborted_reason is not None,
            "termination_reason": aborted_reason,
        }

    def record_and_guard(
        check_id: str, passed: bool, result: dict[str, Any], evidence: dict[str, Any]
    ) -> str | None:
        if result["timed_out"] or result["overflow_stream"] is not None:
            try:
                state = container_state(exact_id)
            except Exception as error:
                state = {
                    "probe_failed": True,
                    "error_type": type(error).__name__,
                    "message_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
                }
            evidence["post_invocation_guard"] = {
                "container": state,
                "runtime_probe_deferred_until_forced_restart": True,
            }
            checks.append(
                {"check_id": check_id, "passed": False, "evidence": evidence}
            )
            if result["timed_out"]:
                return "timeout"
            return f"{result['overflow_stream']}_limit"
        try:
            guard_ok, guard_evidence, reason = post_invocation_guard(
                exact_id, contract
            )
        except Exception as error:
            evidence["post_invocation_guard"] = {
                "probe_failed": True,
                "error_type": type(error).__name__,
                "message_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
            }
            checks.append(
                {"check_id": check_id, "passed": False, "evidence": evidence}
            )
            return "candidate_post_guard_unavailable"
        evidence["post_invocation_guard"] = guard_evidence
        checks.append(
            {
                "check_id": check_id,
                "passed": passed and guard_ok,
                "evidence": evidence,
            }
        )
        if reason is not None:
            return reason
        return None

    for case in hidden["success_cases"]:
        raw = (
            json.dumps(case["payload"], ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode()
        result = candidate_invocation(exact_id, raw, contract, 4)
        durations.append(result["duration_seconds"])
        stdout_sizes.append(result["stdout_bytes"])
        stderr_sizes.append(result["stderr_bytes"])
        parsed = None
        try:
            parsed = load_candidate_json(result["stdout"])
        except (
            CandidateJSONError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
            RecursionError,
        ):
            pass
        passed = (
            not result["timed_out"]
            and result["overflow_stream"] is None
            and result["return_code"] == 0
            and result["stderr"] == b""
            and result["stdout"].endswith(b"\n")
            and strict_json_equal(parsed, normalize_expected(case["payload"]))
        )
        evidence = result_evidence(result)
        reason = record_and_guard(
            f"functional_success_{case['case_id']}", passed, result, evidence
        )
        if reason is not None:
            return checks, current_metrics(reason)

    for case in hidden["error_cases"]:
        if "raw_input" in case:
            raw = case["raw_input"].encode()
        elif "raw_input_repeat" in case:
            repeated = case["raw_input_repeat"]
            raw = repeated["text"].encode() * repeated["count"]
        elif "payload_generator" in case:
            generator = case["payload_generator"]
            if generator != {"kind": "null_records", "count": 50001}:
                raise VerificationError("unknown trusted hidden payload generator")
            raw = (json.dumps({"records": [None] * generator["count"]}, separators=(",", ":")) + "\n").encode()
        else:
            raw = (
                json.dumps(case["payload"], ensure_ascii=False, separators=(",", ":"))
                + "\n"
            ).encode()
        result = candidate_invocation(exact_id, raw, contract, 4)
        durations.append(result["duration_seconds"])
        stdout_sizes.append(result["stdout_bytes"])
        stderr_sizes.append(result["stderr_bytes"])
        parsed = None
        try:
            parsed = load_candidate_json(result["stderr"])
        except (
            CandidateJSONError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            ValueError,
            RecursionError,
        ):
            pass
        expected = {"error": {"code": case["code"], "message": case["message"]}}
        passed = (
            not result["timed_out"]
            and result["overflow_stream"] is None
            and result["return_code"] == 2
            and result["stdout"] == b""
            and result["stderr"].endswith(b"\n")
            and strict_json_equal(parsed, expected)
        )
        evidence = result_evidence(result)
        evidence["observed_error_code"] = (
            parsed.get("error", {}).get("code") if isinstance(parsed, dict) else None
        )
        reason = record_and_guard(
            f"functional_error_{case['case_id']}", passed, result, evidence
        )
        if reason is not None:
            return checks, current_metrics(reason)

    performance = hidden["performance_case"]
    payload = performance_payload(performance)
    raw = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
    result = candidate_invocation(
        exact_id, raw, contract, performance["timeout_seconds"]
    )
    durations.append(result["duration_seconds"])
    stdout_sizes.append(result["stdout_bytes"])
    stderr_sizes.append(result["stderr_bytes"])
    parsed = None
    try:
        parsed = load_candidate_json(result["stdout"])
    except (
        CandidateJSONError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        RecursionError,
    ):
        pass
    passed = (
        not result["timed_out"]
        and result["overflow_stream"] is None
        and result["return_code"] == 0
        and result["stderr"] == b""
        and result["stdout"].endswith(b"\n")
        and strict_json_equal(parsed, normalize_expected(payload))
    )
    evidence = result_evidence(result)
    evidence.update(
        {
            "record_count": performance["record_count"],
            "timeout_seconds": performance["timeout_seconds"],
            "correct_output_required": True,
        }
    )
    reason = record_and_guard(
        "performance_fixed_large_input", passed, result, evidence
    )
    return checks, current_metrics(reason)


def _result(
    *,
    verdict: str,
    source_digest: str,
    contract_hash: str,
    checks: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "nami_work_case10_verifier_result_v3",
        "verdict": verdict,
        "candidate_source_sha256": source_digest,
        "contract_sha256": contract_hash,
        "checks": checks,
        "metrics": metrics,
    }


def verify_candidate(plan_path: Path, candidate_source: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {
        "attempt_count": 0,
        "max_duration_seconds": 0,
        "max_stdout_bytes": 0,
        "max_stderr_bytes": 0,
        "post_restart_process_count": -1,
        "post_restart_runtime_entries": {},
    }
    source_digest = hashlib.sha256(b"candidate_source_not_scanned").hexdigest()
    contract_hash = "0" * 64
    ownership_verified = False
    candidate_mutated = False
    exact_id = ""
    try:
        contract = load_contract()
        contract_hash = contract["contract_sha256"]
        plan = load_plan(plan_path, contract)
        exact_id = plan["candidate_container"]["exact_id"]
        inspect_owned(plan, contract, require_running=True)
        ownership_verified = True
        checks.append(
            {
                "check_id": "ownership_before_mutation",
                "passed": True,
                "evidence": {
                    "exact_id_sha256": hashlib.sha256(exact_id.encode()).hexdigest()
                },
            }
        )
        source_scan = scan_tree_for_contract(
            candidate_source.absolute(), CANDIDATES_ROOT, contract
        )
        source_digest = source_scan["tree_sha256"]
        checks.append(
            {
                "check_id": "candidate_source_bounded_safe_tree",
                "passed": source_scan["safe"],
                "evidence": {
                    key: source_scan[key]
                    for key in (
                        "safe",
                        "reason",
                        "entry_count",
                        "file_count",
                        "directory_count",
                        "total_bytes",
                        "tree_sha256",
                    )
                },
            }
        )
        if not source_scan["safe"]:
            return _result(
                verdict="reject",
                source_digest=source_digest,
                contract_hash=contract_hash,
                checks=checks,
                metrics=metrics,
            )
        require_docker_ok(["stop", "--time", "0", exact_id], 10)
        candidate_mutated = True
        submission = CONTROLLER_ROOT / plan["submission_relative_path"]
        copied_scan = clear_and_copy_source(
            candidate_source.absolute(), submission, source_scan, contract
        )
        checks.append(
            {
                "check_id": "bounded_copy_matches_source",
                "passed": copied_scan["tree_sha256"] == source_scan["tree_sha256"],
                "evidence": {"copied_tree_sha256": copied_scan["tree_sha256"]},
            }
        )
        require_docker_ok(["restart", "--time", "0", exact_id], 10)
        inspect_owned(plan, contract, require_running=True)
        pre_state = ensure_clean_rest(exact_id, contract)
        checks.append(
            {
                "check_id": "pre_attempt_restart_clean",
                "passed": pre_state["clean"],
                "evidence": pre_state,
            }
        )
        static_checks = validate_submission_static(source_scan, contract)
        checks.extend(static_checks)
        if all(item["passed"] for item in static_checks):
            functional_checks, functional_metrics = run_functional_suite(
                exact_id, contract
            )
            checks.extend(functional_checks)
            metrics.update(functional_metrics)
        execution_aborted = bool(metrics.get("execution_aborted"))
        state_before_restart = container_state(exact_id)
        if execution_aborted or not state_before_restart["running"]:
            checks.append(
                {
                    "check_id": "runtime_no_contract_outside_files",
                    "passed": False,
                    "evidence": {
                        "deferred_to_post_restart": True,
                        "termination_reason": metrics.get("termination_reason"),
                        "container": state_before_restart,
                    },
                }
            )
            checks.append(
                {
                    "check_id": "runtime_no_process_leak",
                    "passed": False,
                    "evidence": {
                        "deferred_to_post_restart": True,
                        "termination_reason": metrics.get("termination_reason"),
                    },
                }
            )
        else:
            runtime = runtime_roots_state(exact_id, contract)
            runtime_processes = process_count(exact_id)
            checks.append(
                {
                    "check_id": "runtime_no_contract_outside_files",
                    "passed": runtime["clean"],
                    "evidence": runtime,
                }
            )
            checks.append(
                {
                    "check_id": "runtime_no_process_leak",
                    "passed": runtime_processes
                    == contract["process"]["expected_process_count_at_rest"],
                    "evidence": {"process_count": runtime_processes},
                }
            )
        inspect_owned(plan, contract, require_running=False)
        checks.append(
            {
                "check_id": "ownership_before_post_restart",
                "passed": True,
                "evidence": {"still_exact": True},
            }
        )
        require_docker_ok(["restart", "--time", "0", exact_id], 10)
        inspect_owned(plan, contract, require_running=True)
        post_state = ensure_clean_rest(exact_id, contract)
        metrics["post_restart_process_count"] = post_state["process_count"]
        metrics["post_restart_runtime_entries"] = {
            path: item["entry_count"]
            for path, item in post_state["runtime_roots"]["roots"].items()
        }
        checks.append(
            {
                "check_id": "post_attempt_restart_clean",
                "passed": post_state["clean"],
                "evidence": post_state,
            }
        )
        verdict = "accept" if checks and all(item["passed"] for item in checks) else "reject"
        return _result(
            verdict=verdict,
            source_digest=source_digest,
            contract_hash=contract_hash,
            checks=checks,
            metrics=metrics,
        )
    except (
        VerificationError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        checks.append(
            {
                "check_id": "verifier_infrastructure",
                "passed": False,
                "evidence": {
                    "error_type": type(error).__name__,
                    "message_sha256": hashlib.sha256(str(error).encode()).hexdigest(),
                },
            }
        )
        if ownership_verified and candidate_mutated and exact_id:
            try:
                require_docker_ok(["restart", "--time", "0", exact_id], 10)
            except Exception:
                pass
        return _result(
            verdict="invalid",
            source_digest=source_digest,
            contract_hash=contract_hash,
            checks=checks,
            metrics=metrics,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ownership-plan", required=True)
    parser.add_argument("--candidate-source", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result).absolute()
    if not _inside(result_path, CONTROLLER_ROOT):
        raise SystemExit("result path must remain below /runtime")
    result = verify_candidate(Path(args.ownership_plan), Path(args.candidate_source))
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if result["verdict"] in {"accept", "reject"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
