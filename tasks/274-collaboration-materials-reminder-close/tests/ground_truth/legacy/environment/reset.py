#!/usr/bin/env python3
"""Reset case_20 from immutable synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from pathlib import Path

from state import build_database, logical_state, logical_state_sha256


MARKER = ".case20_runtime"
MAX_RESET_ENTRIES = 4096
MAX_RESET_DEPTH = 64


def make_owned_tree_removable(root: Path) -> None:
    """Bounded, non-following permission repair before deleting an owned runtime."""
    pending: list[tuple[Path, int]] = [(root, 0)]
    observed = 0
    while pending:
        directory, depth = pending.pop()
        if depth > MAX_RESET_DEPTH:
            raise ValueError("owned runtime exceeds reset depth limit")
        os.chmod(directory, 0o700, follow_symlinks=False)
        with os.scandir(directory) as entries:
            for entry in entries:
                observed += 1
                if observed > MAX_RESET_ENTRIES:
                    raise ValueError("owned runtime exceeds reset entry limit")
                mode = entry.stat(follow_symlinks=False).st_mode
                path = Path(entry.path)
                if stat.S_ISDIR(mode):
                    os.chmod(path, 0o700, follow_symlinks=False)
                    pending.append((path, depth + 1))
                elif not stat.S_ISLNK(mode):
                    os.chmod(path, 0o600, follow_symlinks=False)


def safe_reset_root(work_root: Path, case_root: Path) -> Path:
    work_root = work_root.resolve(strict=False)
    case_root = case_root.resolve(strict=True)
    forbidden = {Path("/"), case_root, case_root.parent}
    if work_root in forbidden or len(work_root.parts) < 4:
        raise ValueError("unsafe work root")
    if work_root.exists():
        marker = work_root / MARKER
        if not marker.is_file() or marker.is_symlink():
            raise ValueError("existing work root is not owned by case_20")
        if marker.read_text(encoding="utf-8") != "case_20\n":
            raise ValueError("runtime ownership marker content is invalid")
        if work_root.is_mount() or (work_root / "service.sock").exists():
            raise ValueError("refusing to reset a mounted or active runtime")
        make_owned_tree_removable(work_root)
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, mode=0o700)
    os.chmod(work_root, 0o700)
    (work_root / MARKER).write_text("case_20\n", encoding="utf-8")
    os.chmod(work_root / MARKER, 0o600)
    return work_root


def reset(case_root: Path, work_root: Path) -> dict[str, object]:
    case_root = case_root.resolve(strict=True)
    work_root = safe_reset_root(work_root, case_root)
    workspace = work_root / "workspace"
    service_state = work_root / "service_state"
    shutil.copytree(case_root / "fixtures/workspace_seed", workspace)
    os.chmod(workspace, 0o700)
    inputs = workspace / "inputs"
    for path in sorted(inputs.rglob("*"), reverse=True):
        if path.is_symlink():
            raise ValueError("fixture inputs must not contain symbolic links")
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(inputs, 0o555)
    (workspace / "archive").mkdir(mode=0o700)
    (workspace / "outputs").mkdir(mode=0o700)
    database = service_state / "collaboration.sqlite"
    build_database(case_root, database)
    os.chmod(service_state, 0o700)
    os.chmod(database, 0o600)
    state = logical_state(workspace, database)
    digest = logical_state_sha256(workspace, database)
    payload = {
        "schema_version": "case20_reset_result_v1",
        "workspace": str(workspace),
        "service_database": str(database),
        "initial_state_sha256": digest,
        "logical_state": state,
        "candidate_visibility": {
            "read_write": ["workspace"],
            "read_only": ["environment/tools", "environment/tool_contract.json"],
            "not_mounted": ["oracle", "verifier", "tests", "fixtures", "validation", "service_state"],
        },
    }
    (work_root / "reset_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(work_root / "reset_result.json", 0o600)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    result = reset(args.case_root, args.work_root)
    print(json.dumps({key: value for key, value in result.items() if key != "logical_state"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
