from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create one exact case_08 sandbox")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--host-alias", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--container-name", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--sandbox-contract", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--runtime-workspace", required=True, type=Path)
    return parser.parse_args()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def managed_workspace(runtime_root: Path, runtime_workspace: Path) -> tuple[Path, Path]:
    root = lexical_absolute(runtime_root)
    workspace = lexical_absolute(runtime_workspace)
    if not root.is_dir() or not workspace.is_dir():
        raise ValueError("runtime root and workspace must already be directories")
    require_no_symlink_components(root)
    require_no_symlink_components(workspace)
    if workspace.parent != root:
        raise ValueError("runtime workspace must be an exact child of runtime root")
    if root.resolve(strict=True) != root or workspace.resolve(strict=True) != workspace:
        raise ValueError("managed runtime path must be canonical")
    return root, workspace


def validate_dynamic_id(name: str, value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"{name} contains unsafe characters")
    return value


def main() -> int:
    args = parse_args()
    run_id = validate_dynamic_id("run_id", args.run_id)
    task_id = validate_dynamic_id("task_id", args.task_id)
    host_alias = validate_dynamic_id("host_alias", args.host_alias)
    attempt_id = validate_dynamic_id("attempt_id", args.attempt_id)
    container_name = validate_dynamic_id("container_name", args.container_name)
    runtime_root, workspace = managed_workspace(
        args.runtime_root,
        args.runtime_workspace,
    )
    contract, contract_sha256 = read_contract(args.sandbox_contract)
    labels = {
        "agent_sft.run_id": run_id,
        "agent_sft.task_id": task_id,
        "agent_sft.case_id": str(contract["case_id"]),
        "agent_sft.variant": str(contract["variant"]),
        "agent_sft.host_alias": host_alias,
        "agent_sft.attempt_id": attempt_id,
        "agent_sft.role": str(contract["role"]),
        "agent_sft.sandbox_contract_sha256": contract_sha256,
    }
    scratch = contract["tmpfs"][0]
    tmpfs_options = ",".join(str(item) for item in scratch["options"])
    command = ["docker", "create", "--name", container_name]
    for key, value in sorted(labels.items()):
        command.extend(["--label", f"{key}={value}"])
    command.extend(
        [
            "--user",
            str(contract["user"]),
            "--cpus",
            str(contract["cpu_cores"]),
            "--memory",
            str(contract["memory_bytes"]),
            "--memory-swap",
            str(contract["memory_swap_bytes"]),
            "--pids-limit",
            str(contract["pids_limit"]),
            "--ulimit",
            (
                f"fsize={contract['file_size_limit_bytes']}:"
                f"{contract['file_size_limit_bytes']}"
            ),
            "--ulimit",
            f"nofile={contract['open_files_limit']}:{contract['open_files_limit']}",
            "--network",
            str(contract["network_mode"]),
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--tmpfs",
            f"/scratch:{tmpfs_options},size={scratch['size_bytes']}",
            "--mount",
            (
                f"type=bind,src={workspace},dst=/workspace,"
                "bind-propagation=rprivate"
            ),
            "--workdir",
            "/workspace",
            "--env",
            "HOME=/nonexistent",
            "--env",
            "TMPDIR=/scratch",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONHASHSEED=0",
            "--env",
            "LANG=C.UTF-8",
            "--env",
            "LC_ALL=C.UTF-8",
            "--env",
            "TZ=UTC",
            args.image_id,
        ]
    )
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("docker_create_failed")
    container_id = completed.stdout.strip()
    if len(container_id) != 64:
        raise RuntimeError("docker_create_did_not_return_full_id")
    print(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "container_id": container_id,
                "image_id": args.image_id,
                "name": container_name,
                "runtime_root": runtime_root.as_posix(),
                "runtime_workspace": workspace.as_posix(),
                "sandbox_contract_sha256": contract_sha256,
                "labels": labels,
                "status": "created_not_started",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
