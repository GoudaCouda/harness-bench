#!/usr/bin/env python3
"""Create one exact case_09 workspace from immutable fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("workspace cannot contain symbolic links")
        if path.is_dir():
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
            raise ValueError("workspace cannot contain special files")
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def reset(case_root: Path, workspace: Path) -> str:
    if workspace.exists() or workspace.is_symlink():
        raise FileExistsError("reset target must not already exist")
    fixture_root = case_root / "fixtures"
    initial = fixture_root / "initial_workspace"
    workspace.mkdir(parents=True)
    shutil.copy2(fixture_root / "task.md", workspace / "task.md")
    shutil.copy2(fixture_root / "protocol_contract.json", workspace / "protocol_contract.json")
    shutil.copy2(fixture_root / "seed.db", workspace / "seed.db")
    shutil.copytree(initial / "submission", workspace / "submission", dirs_exist_ok=False)
    return tree_sha256(workspace)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    state_hash = reset(args.case_root.resolve(), args.workspace.resolve())
    payload = {"schema_version": "case09_reset_result_v1", "initial_state_sha256": state_hash}
    if args.result_json:
        args.result_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
