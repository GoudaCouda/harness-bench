#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path


CASE_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = CASE_DIR / "fixtures" / "workspace_seed"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_inventory(root: Path) -> dict[str, list[dict[str, object]]]:
    directories: list[dict[str, object]] = []
    files: list[dict[str, object]] = []

    def visit(directory: Path, prefix: str) -> None:
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            raise ValueError(f"workspace scan failed at {prefix or '.'}: {exc.__class__.__name__}") from exc
        for entry in ordered:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise ValueError(f"workspace lstat failed at {relative}: {exc.__class__.__name__}") from exc
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"unsafe workspace entry: {relative}")
            if stat.S_ISDIR(mode):
                directories.append({"path": relative, "mode": stat.S_IMODE(mode)})
                visit(Path(entry.path), relative)
            else:
                path = Path(entry.path)
                files.append(
                    {
                        "path": relative,
                        "sha256": file_sha256(path),
                        "size_bytes": path.stat().st_size,
                        "mode": stat.S_IMODE(mode),
                    }
                )

    visit(root, "")
    return {"directories": directories, "files": files}


def tree_sha256(root: Path) -> str:
    payload = json.dumps(
        tree_inventory(root),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def safe_target(workspace: Path, allowed_root: Path) -> Path:
    allowed = allowed_root.resolve(strict=True)
    if workspace.is_symlink():
        raise ValueError("workspace reset target must not be a symbolic link")
    parent = workspace.parent.resolve(strict=True)
    expected_parent = (allowed / "workspaces").resolve(strict=True)
    if parent != expected_parent or workspace.name in {"", ".", ".."}:
        raise ValueError("workspace must be one direct test directory below workspaces/")
    resolved = workspace.resolve(strict=False)
    if resolved.parent != expected_parent:
        raise ValueError("workspace reset target escaped the allowed root")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    args = parser.parse_args()
    workspace = safe_target(args.workspace, args.allowed_root)
    if workspace.exists():
        if not workspace.is_dir() or workspace.is_symlink():
            raise ValueError("existing reset target must be a real directory")
        shutil.rmtree(workspace)
    shutil.copytree(SEED_DIR, workspace, copy_function=shutil.copy2)
    for path in workspace.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError("fixture contains an unsafe entry")
        os.chmod(path, 0o755 if stat.S_ISDIR(mode) else 0o644)
    os.chmod(workspace, 0o775)
    inventory = tree_inventory(workspace)
    result = {
        "workspace": str(workspace),
        "initial_state_sha256": tree_sha256(workspace),
        **inventory,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
