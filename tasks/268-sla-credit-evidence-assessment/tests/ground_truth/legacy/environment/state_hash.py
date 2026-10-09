#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, list[dict[str, object]]]:
    directories: list[dict[str, object]] = []
    files: list[dict[str, object]] = []
    unsafe: list[dict[str, object]] = []
    scan_errors: list[dict[str, str]] = []

    def visit(directory: Path, prefix: str) -> None:
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            scan_errors.append({"path": prefix or ".", "error": exc.__class__.__name__})
            return
        for entry in ordered:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                scan_errors.append({"path": relative, "error": exc.__class__.__name__})
                continue
            if stat.S_ISDIR(mode):
                directories.append({"path": relative, "mode": stat.S_IMODE(mode)})
                visit(Path(entry.path), relative)
            elif stat.S_ISREG(mode):
                path = Path(entry.path)
                try:
                    files.append(
                        {
                            "path": relative,
                            "sha256": sha256(path),
                            "size_bytes": path.stat().st_size,
                            "mode": stat.S_IMODE(mode),
                        }
                    )
                except OSError as exc:
                    scan_errors.append({"path": relative, "error": exc.__class__.__name__})
            else:
                unsafe.append({"path": relative, "file_type": stat.S_IFMT(mode)})

    visit(root, "")
    return {
        "directories": directories,
        "files": files,
        "unsafe": unsafe,
        "scan_errors": scan_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    allowed = args.allowed_root.resolve(strict=True)
    expected_parent = (allowed / "workspaces").resolve(strict=True)
    if root.parent != expected_parent:
        raise ValueError("workspace is outside the case test scope")
    observed = inventory(root)
    # A clean workspace must use the same canonical payload as reset.py and the
    # frozen workspace manifest. Unsafe entries and scan errors remain part of
    # the payload when present so mutated states cannot collide with a clean
    # inventory merely because an unreadable subtree was skipped.
    canonical = (
        {"directories": observed["directories"], "files": observed["files"]}
        if not observed["unsafe"] and not observed["scan_errors"]
        else observed
    )
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    print(hashlib.sha256(payload).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
