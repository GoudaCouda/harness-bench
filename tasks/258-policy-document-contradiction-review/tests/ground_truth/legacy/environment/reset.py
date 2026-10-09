#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


CASE_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = CASE_DIR / "fixtures" / "workspace_seed"


def safe_workspace(value: str) -> Path:
    workspace = Path(value).resolve(strict=False)
    if workspace == Path("/") or len(workspace.parts) < 4:
        raise ValueError("workspace path is too broad")
    if workspace == CASE_DIR or CASE_DIR in workspace.parents:
        raise ValueError("workspace must remain outside the immutable case directory")
    return workspace


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("workspace contains a symbolic link")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--result")
    args = parser.parse_args()
    workspace = safe_workspace(args.workspace)
    if workspace.exists() or workspace.is_symlink():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SEED_DIR, workspace, symlinks=False)
    (workspace / "output").mkdir()
    payload = {
        "status": "reset",
        "workspace": str(workspace),
        "initial_state_sha256": tree_hash(workspace),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if args.result:
        result_path = Path(args.result)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
