#!/usr/bin/env python3
"""Deterministically reset the agent-visible workspace from immutable fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = CASE_ROOT / "fixtures" / "agent_workspace"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("symbolic links are forbidden in the workspace")
        if path.is_file():
            result.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": file_sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    return result


def state_sha256(root: Path) -> str:
    payload = json.dumps(
        inventory(root), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_workspace(path: Path) -> Path:
    resolved = path.resolve(strict=False)
    if not resolved.is_absolute() or resolved == Path("/"):
        raise ValueError("workspace must be an absolute scoped path")
    if not str(resolved).startswith("/work/"):
        raise ValueError("workspace must be below the case container /work mount")
    if len(resolved.parts) < 4:
        raise ValueError("workspace path is too broad")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    workspace = validate_workspace(args.workspace)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE_ROOT, workspace)
    result = {
        "schema_version": "nami_work_case05_reset_v1",
        "workspace": str(workspace),
        "file_count": len(inventory(workspace)),
        "state_sha256": state_sha256(workspace),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

