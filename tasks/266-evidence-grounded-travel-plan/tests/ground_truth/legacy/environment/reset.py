#!/usr/bin/env python3
"""从不可变合成 fixture 重置 case_12 的 Agent 可见工作区。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"symbolic link is forbidden: {relative}")
        if path.is_dir():
            digest.update(f"D\0{relative}\0".encode("utf-8"))
        elif path.is_file():
            digest.update(f"F\0{relative}\0{path.stat().st_size}\0".encode("utf-8"))
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        else:
            raise ValueError(f"unsupported workspace entry: {relative}")
    return digest.hexdigest()


def _safe_workspace(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_absolute() or resolved == Path("/"):
        raise ValueError("workspace must be a non-root absolute path")
    if "case_12" not in resolved.as_posix():
        raise ValueError("workspace path must be scoped to case_12")
    return resolved


def reset(case_root: Path, workspace: Path) -> dict[str, object]:
    case_root = case_root.resolve()
    workspace = _safe_workspace(workspace)
    seed = case_root / "fixtures" / "agent_seed"
    if not seed.is_dir() or seed.is_symlink():
        raise ValueError("agent seed is missing or unsafe")
    if workspace.exists():
        if workspace.is_symlink():
            raise ValueError("workspace cannot be a symbolic link")
        shutil.rmtree(workspace)
    shutil.copytree(seed, workspace, copy_function=shutil.copy2)
    (workspace / "output").mkdir()
    runtime = workspace / "runtime"
    runtime.mkdir()
    (runtime / "network_events.jsonl").write_text("", encoding="utf-8")
    state_hash = tree_sha256(workspace)
    return {
        "schema_version": "case12_reset_result_v1",
        "workspace": str(workspace),
        "initial_state_sha256": state_hash,
        "agent_visible_roots": ["input", "output", "runtime"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reset(args.case_root, args.workspace), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
