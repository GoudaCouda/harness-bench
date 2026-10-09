#!/usr/bin/env python3
"""Atomically prepare case_10's editable teacher workspace.

This controller-side entrypoint never exposes the case directory to the teacher
runtime.  It verifies the immutable fixture, constructs a complete replacement
next to the destination, applies explicit ownership/modes, and publishes the
replacement with an atomic rename (or Linux rename-exchange on reset).
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Iterator


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = CASE_ROOT / "fixtures" / "initial_repo"
WORKSPACE_MANIFEST_PATH = CASE_ROOT / "environment" / "workspace_manifest.json"
CONTRACT_PATH = CASE_ROOT / "environment" / "agent_workspace_contract.json"
AT_FDCWD = -100
RENAME_EXCHANGE = 2


class WorkspaceContractError(RuntimeError):
    """A path, fixture, ownership, or atomic-publication contract failed."""


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _require_real_directory(path: Path, label: str) -> None:
    try:
        metadata = os.lstat(path)
    except OSError as error:
        raise WorkspaceContractError(f"{label} is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise WorkspaceContractError(f"{label} must be a real directory")


def validate_managed_target(target: Path, allowed_root: Path) -> tuple[Path, Path]:
    """Return normalized paths after rejecting escape and symlink ancestors."""

    target = _absolute(target)
    allowed_root = _absolute(allowed_root)
    _require_real_directory(allowed_root, "allowed root")
    if target == allowed_root:
        raise WorkspaceContractError("managed target must be a strict child of allowed root")
    try:
        inside = os.path.commonpath([os.fspath(target), os.fspath(allowed_root)]) == os.fspath(
            allowed_root
        )
    except ValueError as error:
        raise WorkspaceContractError("managed target and allowed root are incompatible") from error
    if not inside:
        raise WorkspaceContractError("managed target escapes allowed root")
    current = allowed_root
    relative_parts = target.relative_to(allowed_root).parts
    for part in relative_parts[:-1]:
        current = current / part
        _require_real_directory(current, "managed target parent")
    if _lexists(target):
        metadata = os.lstat(target)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise WorkspaceContractError("existing managed target must be a real directory")
    return target, allowed_root


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _legacy_tree_hash(root: Path) -> str:
    """Match the initial_state_sha256 algorithm already used by case_10."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            raise WorkspaceContractError(f"fixture symlink forbidden: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            digest.update(f"D\0{relative}\0".encode())
        elif stat.S_ISREG(metadata.st_mode):
            digest.update(f"F\0{relative}\0{metadata.st_size}\0".encode())
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
        else:
            raise WorkspaceContractError(f"fixture special entry forbidden: {relative}")
    return digest.hexdigest()


def verify_fixture() -> tuple[dict[str, object], str]:
    manifest = json.loads(WORKSPACE_MANIFEST_PATH.read_text(encoding="utf-8"))
    declared = {item["path"]: item for item in manifest["files"]}
    observed_files: set[str] = set()
    for path in FIXTURE_ROOT.rglob("*"):
        relative = path.relative_to(FIXTURE_ROOT).as_posix()
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            raise WorkspaceContractError(f"fixture symlink forbidden: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise WorkspaceContractError(f"fixture entry is not an independent regular file: {relative}")
        observed_files.add(relative)
        expected = declared.get(relative)
        if expected is None:
            raise WorkspaceContractError(f"fixture contains undeclared file: {relative}")
        if metadata.st_size != expected["size_bytes"] or _file_sha256(path) != expected["sha256"]:
            raise WorkspaceContractError(f"fixture hash or size mismatch: {relative}")
    if observed_files != set(declared):
        raise WorkspaceContractError("fixture file inventory does not match workspace manifest")
    state_hash = _legacy_tree_hash(FIXTURE_ROOT)
    if state_hash != manifest["initial_state_sha256"]:
        raise WorkspaceContractError("fixture initial-state hash mismatch")
    return manifest, state_hash


def _safe_chown(path: Path, uid: int, gid: int) -> None:
    try:
        os.chown(path, uid, gid, follow_symlinks=False)
    except OSError as error:
        raise WorkspaceContractError(f"cannot apply requested ownership to {path.name}") from error


def apply_workspace_policy(
    root: Path,
    *,
    agent_uid: int,
    agent_gid: int,
    controller_uid: int,
    controller_gid: int,
) -> None:
    editable_file = root / "src" / "process.js"
    editable_directory = root / "src"
    paths = sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True)
    for path in paths:
        metadata = os.lstat(path)
        if stat.S_ISLNK(metadata.st_mode):
            raise WorkspaceContractError("workspace policy refuses symlinks")
        is_editable = path in {editable_file, editable_directory}
        uid = agent_uid if is_editable else controller_uid
        gid = agent_gid if is_editable else controller_gid
        _safe_chown(path, uid, gid)
        if stat.S_ISDIR(metadata.st_mode):
            path.chmod(0o755 if path == editable_directory else 0o555)
        elif stat.S_ISREG(metadata.st_mode):
            path.chmod(0o644 if path == editable_file else 0o444)
        else:
            raise WorkspaceContractError("workspace policy refuses special entries")
    _safe_chown(root, controller_uid, controller_gid)
    root.chmod(0o555)


def _remove_entry_at(parent_fd: int, name: str) -> None:
    """Remove one fd-relative entry without following a contained symlink."""

    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        os.unlink(name, dir_fd=parent_fd)
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(directory_fd)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise WorkspaceContractError("cleanup directory changed while opening")
        os.fchmod(directory_fd, 0o700)
        with os.scandir(directory_fd) as iterator:
            children = sorted(entry.name for entry in iterator)
        for child in children:
            _remove_entry_at(directory_fd, child)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise WorkspaceContractError("cleanup directory changed during removal")
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)


def _remove_tree_force(path: Path) -> None:
    """Remove one exact temporary/old tree without following contained symlinks."""

    if not _lexists(path):
        return
    path = _absolute(path)
    parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    parent_fd = os.open(path.parent, parent_flags)
    try:
        _remove_entry_at(parent_fd, path.name)
    finally:
        os.close(parent_fd)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_exchange(left: Path, right: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise WorkspaceContractError("atomic reset requires Linux renameat2(RENAME_EXCHANGE)")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    result = function(
        AT_FDCWD,
        os.fsencode(left),
        AT_FDCWD,
        os.fsencode(right),
        RENAME_EXCHANGE,
    )
    if result != 0:
        observed_errno = ctypes.get_errno()
        raise WorkspaceContractError(
            f"atomic directory exchange failed with errno {observed_errno}"
        ) from OSError(observed_errno, os.strerror(observed_errno))


def _atomic_publish_directory(staged: Path, destination: Path) -> None:
    """Publish staged atomically; on replacement, staged becomes the old tree."""

    if staged.parent != destination.parent:
        raise WorkspaceContractError("atomic publication requires a same-directory stage")
    staged_metadata = os.lstat(staged)
    if not stat.S_ISDIR(staged_metadata.st_mode) or stat.S_ISLNK(staged_metadata.st_mode):
        raise WorkspaceContractError("publication stage must be a real directory")
    if _lexists(destination):
        destination_metadata = os.lstat(destination)
        if stat.S_ISLNK(destination_metadata.st_mode) or not stat.S_ISDIR(
            destination_metadata.st_mode
        ):
            raise WorkspaceContractError("publication destination must be a real directory")
        _rename_exchange(staged, destination)
        published = os.lstat(destination)
        if (published.st_dev, published.st_ino) != (
            staged_metadata.st_dev,
            staged_metadata.st_ino,
        ):
            raise WorkspaceContractError("atomic exchange published an unexpected inode")
        _remove_tree_force(staged)
    else:
        try:
            os.rename(staged, destination)
        except FileExistsError as error:
            raise WorkspaceContractError("publication destination appeared concurrently") from error
        published = os.lstat(destination)
        if (published.st_dev, published.st_ino) != (
            staged_metadata.st_dev,
            staged_metadata.st_ino,
        ):
            raise WorkspaceContractError("atomic rename published an unexpected inode")
    _fsync_directory(destination.parent)


@contextlib.contextmanager
def exclusive_workspace_lock(lock_path: Path) -> Iterator[None]:
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise WorkspaceContractError("cannot open workspace lock") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise WorkspaceContractError("workspace lock must be one regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise WorkspaceContractError("workspace lock is already held") from error
            raise
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def prepare_agent_workspace(
    *,
    workspace: Path,
    allowed_root: Path,
    agent_uid: int,
    agent_gid: int,
    controller_uid: int,
    controller_gid: int,
) -> dict[str, object]:
    for value in (agent_uid, agent_gid, controller_uid, controller_gid):
        if value < 0:
            raise WorkspaceContractError("uid and gid values must be non-negative")
    workspace, allowed_root = validate_managed_target(workspace, allowed_root)
    verify_fixture()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    lock_path = workspace.parent / contract["path_policy"]["lock_filename"]
    with exclusive_workspace_lock(lock_path):
        stage = Path(
            tempfile.mkdtemp(prefix=".agent-workspace.prepare.", dir=os.fspath(workspace.parent))
        )
        try:
            shutil.copytree(FIXTURE_ROOT, stage, dirs_exist_ok=True, symlinks=False)
            apply_workspace_policy(
                stage,
                agent_uid=agent_uid,
                agent_gid=agent_gid,
                controller_uid=controller_uid,
                controller_gid=controller_gid,
            )
            state_hash = _legacy_tree_hash(stage)
            expected_hash = contract["fixture"]["initial_state_sha256"]
            if state_hash != expected_hash:
                raise WorkspaceContractError("prepared workspace does not match immutable fixture")
            _atomic_publish_directory(stage, workspace)
        finally:
            if _lexists(stage):
                _remove_tree_force(stage)
    return {
        "schema_version": "nami_work_case10_workspace_prepare_result_v1",
        "case_id": "case_10",
        "workspace": workspace.as_posix(),
        "initial_state_sha256": state_hash,
        "agent_uid": agent_uid,
        "agent_gid": agent_gid,
        "controller_uid": controller_uid,
        "controller_gid": controller_gid,
        "editable_path": "src/process.js",
        "atomic_publish": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowed-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--agent-uid", required=True, type=int)
    parser.add_argument("--agent-gid", required=True, type=int)
    parser.add_argument("--controller-uid", required=True, type=int)
    parser.add_argument("--controller-gid", required=True, type=int)
    arguments = parser.parse_args()
    try:
        result = prepare_agent_workspace(
            workspace=Path(arguments.workspace),
            allowed_root=Path(arguments.allowed_root),
            agent_uid=arguments.agent_uid,
            agent_gid=arguments.agent_gid,
            controller_uid=arguments.controller_uid,
            controller_gid=arguments.controller_gid,
        )
    except WorkspaceContractError as error:
        parser.exit(2, f"workspace preparation rejected: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
