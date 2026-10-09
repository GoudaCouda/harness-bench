#!/usr/bin/env python3
"""Generate the immutable initial-workspace contract from one fresh reset."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path


CASE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = CASE_ROOT / "environment/workspace_manifest.json"
REQUIRED_OUTPUTS = [
    "outputs/standardized/market_brief.pptx",
    "outputs/standardized/project_update.pptx",
    "outputs/standardized/service_review.pptx",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            kind, value = "D", ""
        elif stat.S_ISREG(mode):
            kind, value = "F", sha256_file(path)
        else:
            raise ValueError("initial_workspace_contains_unsafe_entry")
        digest.update(f"{kind}\0{relative}\0{value}\n".encode())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    directories: list[str] = []
    protected_files: list[dict[str, object]] = []
    for path in sorted(workspace.rglob("*"), key=lambda item: item.relative_to(workspace).as_posix()):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            raise SystemExit("initial_workspace_symlink_forbidden")
        if path.is_dir():
            directories.append(relative)
        elif path.is_file():
            protected_files.append({"path": relative, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
        else:
            raise SystemExit("initial_workspace_special_file_forbidden")
    value = {
        "schema_version": "case06_workspace_manifest_v1",
        "generated_at": "2026-07-20T00:00:00Z",
        "initial_state_sha256": tree_hash(workspace),
        "directories": directories,
        "protected_files": protected_files,
        "required_outputs": REQUIRED_OUTPUTS,
    }
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(value["initial_state_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

