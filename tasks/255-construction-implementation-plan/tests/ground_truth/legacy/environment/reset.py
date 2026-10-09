"""Reset one exact case_01 workspace from immutable synthetic fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


CASE_ID = "case_01"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def state_hash(workspace: Path) -> str:
    records: list[bytes] = []
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            raise ValueError("workspace may not contain symbolic links")
        if path.is_dir():
            records.append(f"D\0{relative}\n".encode("utf-8"))
        elif path.is_file():
            records.append(f"F\0{relative}\0{sha256_file(path)}\n".encode("utf-8"))
    return hashlib.sha256(b"".join(records)).hexdigest()


def reset(case_root: Path, workspace: Path, token: str) -> str:
    if token != CASE_ID:
        raise ValueError("exact case reset token is required")
    case_root = case_root.resolve()
    workspace = workspace.resolve()
    if len(workspace.parts) < 3 or workspace in {Path("/"), case_root} or not workspace.name.startswith("case01_"):
        raise ValueError("unsafe workspace path")
    if workspace.exists():
        marker = workspace / ".case_id"
        if not marker.is_file() or marker.read_text(encoding="utf-8") != CASE_ID + "\n":
            raise ValueError("refusing to reset an unowned workspace")
        shutil.rmtree(workspace)
    (workspace / "inputs").mkdir(parents=True)
    (workspace / "outputs").mkdir()
    (workspace / ".case_id").write_text(CASE_ID + "\n", encoding="utf-8")
    source = case_root / "fixtures/input"
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.is_symlink():
            raise ValueError("fixtures must contain regular files only")
        shutil.copyfile(path, workspace / "inputs" / path.name)
    return state_hash(workspace)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--allow-reset-token", required=True)
    args = parser.parse_args()
    digest = reset(args.case_root, args.workspace, args.allow_reset_token)
    print(json.dumps({"case_id": CASE_ID, "initial_state_sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
