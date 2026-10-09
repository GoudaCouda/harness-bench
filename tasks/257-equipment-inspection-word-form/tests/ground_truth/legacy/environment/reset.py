#!/usr/bin/env python3
"""Reset case_03 into an exact Agent-visible workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


VISIBLE_FILES = {
    "fixtures/hospital_header.json": "input/hospital_header.json",
    "fixtures/equipment_registry.json": "input/equipment_registry.json",
    "fixtures/inspection_standard.json": "input/inspection_standard.json",
    "fixtures/instruction.md": "task/instruction.md",
    "environment/docx_writer.py": "tools/docx_writer.py",
    "fixtures/tool_contract.json": "tools/tool_contract.json",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_digest(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            raise ValueError("workspace contains a symbolic link")
        if path.is_dir():
            digest.update(f"D\0{relative}\0{path.stat().st_mode & 0o777:o}\n".encode())
        elif path.is_file():
            digest.update(f"F\0{relative}\0{path.stat().st_mode & 0o777:o}\0{file_sha256(path)}\n".encode())
        else:
            raise ValueError("workspace contains an unsupported filesystem object")
    return digest.hexdigest()


def reset(case_root: Path, workspace: Path) -> str:
    case_root = case_root.resolve()
    workspace = workspace.resolve()
    if workspace.exists() or workspace.is_symlink():
        raise ValueError("workspace target must not already exist")
    workspace.mkdir(parents=True, mode=0o750)
    for directory in ("input", "output", "task", "tools"):
        (workspace / directory).mkdir(mode=0o750)
    for source_name, destination_name in VISIBLE_FILES.items():
        source = case_root / source_name
        destination = workspace / destination_name
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"invalid immutable fixture: {source_name}")
        shutil.copyfile(source, destination)
        destination.chmod(0o550 if destination_name == "tools/docx_writer.py" else 0o440)
    (workspace / "output").chmod(0o750)
    return workspace_digest(workspace)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--case-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    digest = reset(args.case_root, args.workspace)
    print(json.dumps({"schema_version": "case03_reset_result_v1", "initial_state_sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
