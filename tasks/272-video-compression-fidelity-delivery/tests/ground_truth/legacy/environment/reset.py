#!/usr/bin/env python3
"""Reset a case_18 workspace from immutable project-owned fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_inventory(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            kind = "symlink"
            item: dict[str, object] = {
                "path": relative,
                "kind": kind,
                "target": os.readlink(path),
            }
        elif stat.S_ISDIR(mode):
            item = {"path": relative, "kind": "directory"}
        elif stat.S_ISREG(mode):
            item = {
                "path": relative,
                "kind": "file",
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        else:
            item = {"path": relative, "kind": "special"}
        entries.append(item)
    return entries


def state_sha256(root: Path) -> str:
    payload = json.dumps(
        workspace_inventory(root),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def clear_directory(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("workspace must be an existing real directory")
    if root.resolve() == Path("/"):
        raise ValueError("refusing to reset filesystem root")
    for entry in list(root.iterdir()):
        if entry.is_symlink() or entry.is_file():
            entry.unlink()
        elif entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def copy_real_file(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError("fixture source must be a real regular file")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()

    case_root = args.case_root.resolve(strict=True)
    workspace = args.workspace.resolve(strict=True)
    clear_directory(workspace)

    mapping = {
        case_root / "fixtures/source/source.mp4": workspace / "input/source.mp4",
        case_root / "fixtures/task/instruction.md": workspace / "task/instruction.md",
        case_root / "fixtures/task/target_spec.json": workspace / "task/target_spec.json",
        case_root / "environment/tool_contract.json": workspace / "task/tool_contract.json",
    }
    for source, target in mapping.items():
        copy_real_file(source, target)
    (workspace / "output").mkdir()

    inventory = workspace_inventory(workspace)
    result = {
        "initial_state_sha256": state_sha256(workspace),
        "entry_count": len(inventory),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
