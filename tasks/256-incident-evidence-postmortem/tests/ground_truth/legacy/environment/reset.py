#!/usr/bin/env python3
"""Reset case_02 from immutable visible fixtures and report a stable state hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def snapshot(workspace: Path) -> dict[str, Any]:
    directories: list[str] = []
    files: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            raise ValueError("workspace cannot contain symbolic links")
        if path.is_dir():
            directories.append(relative)
        elif path.is_file():
            files.append(
                {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    payload = {"directories": directories, "files": files}
    payload["state_sha256"] = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return payload


def _safe_workspace(workspace: Path, allowed_root: Path) -> Path:
    root = allowed_root.resolve()
    target = workspace.resolve(strict=False)
    if target == root:
        raise ValueError("workspace must be a child of allowed_root")
    target.relative_to(root)
    return target


def reset(case_root: Path, workspace: Path, allowed_root: Path) -> dict[str, Any]:
    target = _safe_workspace(workspace, allowed_root)
    source = (case_root / "fixtures/agent_visible").resolve()
    case_root_resolved = case_root.resolve()
    source.relative_to(case_root_resolved)
    manifest = json.loads(
        (case_root / "environment/workspace_manifest.json").read_text(encoding="utf-8")
    )
    for item in manifest["fixture_files"]:
        fixture = case_root / item["source_path"]
        if fixture.is_symlink() or not fixture.is_file():
            raise ValueError("fixture is missing or unsafe")
        if sha256_file(fixture) != item["sha256"]:
            raise ValueError("fixture hash mismatch")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, copy_function=shutil.copy2)
    (target / "output").mkdir()
    state = snapshot(target)
    if state["state_sha256"] != manifest["initial_state_sha256"]:
        raise ValueError("reset state does not match the frozen initial state")
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    args = parser.parse_args()
    result = reset(args.case_root, args.workspace, args.allowed_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
