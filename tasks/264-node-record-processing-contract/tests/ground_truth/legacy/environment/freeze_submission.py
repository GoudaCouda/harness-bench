#!/usr/bin/env python3
"""Freeze a quiescent case_10 teacher workspace into read-only staging."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from prepare_agent_workspace import (
    CASE_ROOT,
    CONTRACT_PATH,
    FIXTURE_ROOT,
    WorkspaceContractError,
    _absolute,
    _atomic_publish_directory,
    _lexists,
    _remove_tree_force,
    _safe_chown,
    exclusive_workspace_lock,
    validate_managed_target,
)


EDITABLE_PATH = "src/process.js"


def _canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _open_directory_at(parent_fd: int, name: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(name, flags, dir_fd=parent_fd)


def _read_regular_at(parent_fd: int, name: str, expected: os.stat_result) -> tuple[str, bytes]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_dev != expected.st_dev
            or opened.st_ino != expected.st_ino
            or opened.st_size != expected.st_size
        ):
            raise WorkspaceContractError("source changed while opening a regular file")
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        observed = 0
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            observed += len(chunk)
            digest.update(chunk)
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            observed != expected.st_size
            or after.st_dev != opened.st_dev
            or after.st_ino != opened.st_ino
            or after.st_size != opened.st_size
            or after.st_nlink != 1
        ):
            raise WorkspaceContractError("source changed while reading a regular file")
        return digest.hexdigest(), b"".join(chunks)
    finally:
        os.close(descriptor)


def bounded_scan(root: Path, allowed_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    root, allowed_root = validate_managed_target(root, allowed_root)
    descriptors: list[dict[str, Any]] = []
    file_bytes: dict[str, bytes] = {}
    total_bytes = 0
    root_fd = os.open(
        root,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )

    def walk(directory_fd: int, prefix: str, parent_depth: int) -> None:
        nonlocal total_bytes
        try:
            with os.scandir(directory_fd) as iterator:
                names = sorted((entry.name for entry in iterator))
        except OSError as error:
            raise WorkspaceContractError("source directory cannot be enumerated") from error
        for name in names:
            relative = f"{prefix}/{name}" if prefix else name
            depth = parent_depth + 1
            if len(descriptors) >= policy["max_entries"]:
                raise WorkspaceContractError("source entry limit exceeded")
            if len(relative.encode("utf-8", errors="surrogatepass")) > policy[
                "max_relative_path_bytes"
            ]:
                raise WorkspaceContractError("source relative path limit exceeded")
            if depth > policy["max_depth"]:
                raise WorkspaceContractError("source depth limit exceeded")
            try:
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as error:
                raise WorkspaceContractError("source entry cannot be inspected") from error
            if stat.S_ISLNK(metadata.st_mode):
                raise WorkspaceContractError(f"source symlink forbidden: {relative}")
            if stat.S_ISDIR(metadata.st_mode):
                child_fd = _open_directory_at(directory_fd, name)
                try:
                    opened = os.fstat(child_fd)
                    if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                        raise WorkspaceContractError("source directory changed during scan")
                    descriptors.append({"path": relative, "type": "directory"})
                    walk(child_fd, relative, depth)
                finally:
                    os.close(child_fd)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkspaceContractError(f"source special entry forbidden: {relative}")
            if metadata.st_nlink != 1:
                raise WorkspaceContractError(f"source hardlink forbidden: {relative}")
            if metadata.st_size > policy["max_single_file_bytes"]:
                raise WorkspaceContractError(f"source file limit exceeded: {relative}")
            total_bytes += metadata.st_size
            if total_bytes > policy["max_total_bytes"]:
                raise WorkspaceContractError("source total byte limit exceeded")
            digest, content = _read_regular_at(directory_fd, name, metadata)
            descriptors.append(
                {
                    "path": relative,
                    "type": "file",
                    "size": metadata.st_size,
                    "sha256": digest,
                }
            )
            file_bytes[relative] = content

    try:
        walk(root_fd, "", 0)
    finally:
        os.close(root_fd)
    descriptors.sort(key=lambda item: (item["path"], item["type"]))
    canonical = {"entries": descriptors, "reason": None, "total_bytes": total_bytes}
    return {
        "safe": True,
        "entry_count": len(descriptors),
        "file_count": sum(item["type"] == "file" for item in descriptors),
        "directory_count": sum(item["type"] == "directory" for item in descriptors),
        "total_bytes": total_bytes,
        "entries": descriptors,
        "file_bytes": file_bytes,
        "tree_sha256": _canonical_json_sha256(canonical),
    }


def _shape(scan: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item["path"], item["type"]) for item in scan["entries"]]


def _hashes(scan: dict[str, Any]) -> dict[str, str]:
    return {
        item["path"]: item["sha256"]
        for item in scan["entries"]
        if item["type"] == "file"
    }


def validate_complete_candidate(
    candidate_scan: dict[str, Any], fixture_scan: dict[str, Any]
) -> None:
    if _shape(candidate_scan) != _shape(fixture_scan):
        raise WorkspaceContractError("candidate repository inventory differs from fixture")
    candidate_hashes = _hashes(candidate_scan)
    fixture_hashes = _hashes(fixture_scan)
    changed_protected = sorted(
        path
        for path, expected in fixture_hashes.items()
        if path != EDITABLE_PATH and candidate_hashes.get(path) != expected
    )
    if changed_protected:
        raise WorkspaceContractError("candidate modified a protected repository file")
    if EDITABLE_PATH not in candidate_hashes:
        raise WorkspaceContractError("candidate editable source is missing")


def _write_all(descriptor: int, content: bytes) -> None:
    position = 0
    while position < len(content):
        written = os.write(descriptor, content[position:])
        if written <= 0:
            raise WorkspaceContractError("short write while freezing submission")
        position += written


def copy_admitted_tree(
    scan: dict[str, Any], destination: Path, *, owner_uid: int, owner_gid: int
) -> None:
    directories = [item["path"] for item in scan["entries"] if item["type"] == "directory"]
    files = [item["path"] for item in scan["entries"] if item["type"] == "file"]
    for relative in sorted(directories, key=lambda value: (value.count("/"), value)):
        path = destination / relative
        path.mkdir(mode=0o700)
    for relative in sorted(files):
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(descriptor, scan["file_bytes"][relative])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _safe_chown(path, owner_uid, owner_gid)
        path.chmod(0o444)
    for relative in sorted(directories, key=lambda value: (value.count("/"), value), reverse=True):
        path = destination / relative
        _safe_chown(path, owner_uid, owner_gid)
        path.chmod(0o555)
    _safe_chown(destination, owner_uid, owner_gid)
    destination.chmod(0o555)


def freeze_submission(
    *,
    workspace: Path,
    submission: Path,
    allowed_root: Path,
    owner_uid: int,
    owner_gid: int,
    agent_stopped: bool,
) -> dict[str, Any]:
    if not agent_stopped:
        raise WorkspaceContractError("freeze requires an explicit stopped-agent assertion")
    if owner_uid < 0 or owner_gid < 0:
        raise WorkspaceContractError("uid and gid values must be non-negative")
    workspace, allowed_root = validate_managed_target(workspace, allowed_root)
    submission, _ = validate_managed_target(submission, allowed_root)
    if workspace == submission:
        raise WorkspaceContractError("workspace and submission must be different paths")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    policy = contract["freeze_policy"]
    lock_path = workspace.parent / contract["path_policy"]["lock_filename"]
    with exclusive_workspace_lock(lock_path):
        fixture_scan = bounded_scan(FIXTURE_ROOT, CASE_ROOT / "fixtures", policy)
        source_before = bounded_scan(workspace, allowed_root, policy)
        validate_complete_candidate(source_before, fixture_scan)
        stage = Path(
            tempfile.mkdtemp(prefix=".submission.freeze.", dir=os.fspath(submission.parent))
        )
        try:
            copy_admitted_tree(
                source_before, stage, owner_uid=owner_uid, owner_gid=owner_gid
            )
            source_after = bounded_scan(workspace, allowed_root, policy)
            if source_after["tree_sha256"] != source_before["tree_sha256"]:
                raise WorkspaceContractError("candidate workspace changed during freeze")
            frozen_scan = bounded_scan(stage, allowed_root, policy)
            validate_complete_candidate(frozen_scan, fixture_scan)
            if frozen_scan["tree_sha256"] != source_before["tree_sha256"]:
                raise WorkspaceContractError("frozen staging differs from admitted workspace")
            _atomic_publish_directory(stage, submission)
        finally:
            if _lexists(stage):
                _remove_tree_force(stage)
        published_scan = bounded_scan(submission, allowed_root, policy)
        if published_scan["tree_sha256"] != source_before["tree_sha256"]:
            raise WorkspaceContractError("published submission hash mismatch")
    return {
        "schema_version": "nami_work_case10_submission_freeze_result_v1",
        "case_id": "case_10",
        "workspace": _absolute(workspace).as_posix(),
        "submission": _absolute(submission).as_posix(),
        "candidate_tree_sha256": source_before["tree_sha256"],
        "submission_tree_sha256": published_scan["tree_sha256"],
        "editable_source_sha256": _hashes(published_scan)[EDITABLE_PATH],
        "entry_count": published_scan["entry_count"],
        "total_bytes": published_scan["total_bytes"],
        "agent_stopped_asserted": True,
        "atomic_publish": True,
        "readonly_modes_applied": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowed-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--owner-uid", required=True, type=int)
    parser.add_argument("--owner-gid", required=True, type=int)
    parser.add_argument("--agent-stopped", action="store_true")
    arguments = parser.parse_args()
    try:
        result = freeze_submission(
            workspace=Path(arguments.workspace),
            submission=Path(arguments.submission),
            allowed_root=Path(arguments.allowed_root),
            owner_uid=arguments.owner_uid,
            owner_gid=arguments.owner_gid,
            agent_stopped=arguments.agent_stopped,
        )
    except WorkspaceContractError as error:
        parser.exit(2, f"submission freeze rejected: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
