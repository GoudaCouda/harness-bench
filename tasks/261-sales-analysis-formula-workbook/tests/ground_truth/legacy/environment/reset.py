#!/usr/bin/env python3
"""Reset a case_07 workspace from immutable fixtures and print its state hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
from pathlib import Path


def state_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError("workspace contains a symbolic link or special file")
        kind = "d" if path.is_dir() else "f"
        digest.update(f"{kind}\0{relative}\0".encode())
        if path.is_file():
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    target = args.target.resolve(strict=False)
    if target == Path("/") or target.name != "workspace" or "case_07" not in target.parts:
        raise SystemExit("refusing unsafe reset target")
    if target.is_symlink():
        raise SystemExit("refusing symbolic reset target")
    source = Path(__file__).resolve().parents[1] / "fixtures" / "workspace_seed"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=False)
    (target / "output").mkdir()
    value = state_hash(target)
    print(json.dumps({"status": "ok", "target": str(target), "initial_state_sha256": value}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
