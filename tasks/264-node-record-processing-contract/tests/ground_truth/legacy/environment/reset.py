#!/usr/bin/env python3
"""Reset a candidate repository from the immutable synthetic fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from prepare_agent_workspace import prepare_agent_workspace


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = CASE_ROOT / "fixtures" / "initial_repo"


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise RuntimeError(f"symlink forbidden: {relative}")
        if path.is_dir():
            digest.update(f"D\0{relative}\0".encode())
        elif path.is_file():
            digest.update(f"F\0{relative}\0{path.stat().st_size}\0".encode())
            digest.update(path.read_bytes())
        else:
            raise RuntimeError(f"unsupported entry: {relative}")
    return digest.hexdigest()


def ensure_safe_destination(destination: Path, allowed_root: Path) -> None:
    if not destination.is_absolute() or destination == allowed_root:
        raise RuntimeError("destination must be an absolute child of allowed root")
    if os.path.commonpath([str(destination), str(allowed_root)]) != str(allowed_root):
        raise RuntimeError("destination escapes allowed root")
    current = allowed_root
    for part in destination.relative_to(allowed_root).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise RuntimeError(f"symlink component forbidden: {current}")


def reset(destination: Path, allowed_root: Path) -> str:
    destination = destination.absolute()
    allowed_root = allowed_root.absolute()
    ensure_safe_destination(destination, allowed_root)
    identity_uid = os.getuid()
    identity_gid = os.getgid()
    prepared = prepare_agent_workspace(
        workspace=destination,
        allowed_root=allowed_root,
        agent_uid=identity_uid,
        agent_gid=identity_gid,
        controller_uid=identity_uid,
        controller_gid=identity_gid,
    )
    return str(prepared["initial_state_sha256"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True)
    parser.add_argument("--allowed-root", required=True)
    args = parser.parse_args()
    destination = Path(args.destination)
    state_sha256 = reset(destination, Path(args.allowed_root))
    print(json.dumps({"destination": destination.as_posix(), "initial_state_sha256": state_sha256}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
