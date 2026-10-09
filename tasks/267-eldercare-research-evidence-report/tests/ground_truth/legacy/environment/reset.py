#!/usr/bin/env python3
"""Create a deterministic agent-visible workspace from the case fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


VISIBLE_FILES = (
    "LICENSE.txt",
    "metadata.json",
    "report_template.md",
    "source_manifest.json",
    "corpus/S01_demographics_zh.md",
    "corpus/S02_needs_survey_zh.md",
    "corpus/S03_supply_registry_zh.csv",
    "corpus/S04_policy_zh.md",
    "corpus/S05_unit_costs_zh.md",
    "corpus/S06_pilot_en.md",
    "corpus/S07_audit_en.md",
    "corpus/S08_superseded_memo_zh.md",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"symbolic links are forbidden: {relative}")
        if path.is_dir():
            digest.update(f"D\0{relative}\0".encode())
        elif path.is_file():
            digest.update(f"F\0{relative}\0{file_sha256(path)}\0".encode())
        else:
            raise ValueError(f"special files are forbidden: {relative}")
    return digest.hexdigest()


def reset(case_root: Path, work_root: Path) -> dict[str, object]:
    case_root = case_root.resolve(strict=True)
    fixtures = case_root / "fixtures"
    if work_root.exists() or work_root.is_symlink():
        raise ValueError("work root must not already exist")
    work_root.parent.mkdir(parents=True, exist_ok=True)
    staging = work_root.with_name(f".{work_root.name}.building-{os.getpid()}")
    if staging.exists() or staging.is_symlink():
        raise ValueError("staging work root already exists")
    try:
        staging.mkdir(mode=0o750)
        input_root = staging / "input"
        output_root = staging / "output"
        input_root.mkdir(mode=0o750)
        output_root.mkdir(mode=0o750)
        for relative in VISIBLE_FILES:
            source = fixtures / relative
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"fixture missing or unsafe: {relative}")
            destination = input_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            destination.chmod(0o444)
        for directory in sorted(
            (path for path in input_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            directory.chmod(0o555)
        input_root.chmod(0o555)
        manifest = json.loads((case_root / "environment/workspace_seed_manifest.json").read_text())
        actual_files = {
            path.relative_to(input_root).as_posix(): file_sha256(path)
            for path in sorted(input_root.rglob("*"))
            if path.is_file()
        }
        expected_files = {item["path"]: item["sha256"] for item in manifest["files"]}
        if actual_files != expected_files:
            raise ValueError("visible fixture hash set does not match the seed manifest")
        state_hash = tree_sha256(staging)
        if state_hash != manifest["initial_state_sha256"]:
            raise ValueError("initial workspace hash does not match the seed manifest")
        staging.rename(work_root)
    except Exception:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    return {
        "workspace": work_root.as_posix(),
        "initial_state_sha256": state_hash,
        "visible_file_count": len(actual_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reset(args.case_root, args.work_root), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
