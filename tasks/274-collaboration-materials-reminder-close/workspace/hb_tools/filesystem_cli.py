#!/usr/bin/env python3
"""Constrained workspace reader for case_20."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path


def safe_path(workspace: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("unsafe workspace path")
    current = workspace
    for part in relative.parts:
        current = current / part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("symbolic links are forbidden")
    path = current.resolve(strict=True)
    path.relative_to(workspace)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(prog="filesystem_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list-tree")
    list_parser.add_argument("--path", default="inputs")
    read_parser = sub.add_parser("read-text")
    read_parser.add_argument("--path", required=True)
    hash_parser = sub.add_parser("sha256")
    hash_parser.add_argument("--path", required=True)
    try:
        args = parser.parse_args()
        value = os.environ.get("CASE20_WORKSPACE")
        if not value:
            raise ValueError("CASE20_WORKSPACE must be set")
        workspace = Path(value).resolve(strict=True)
        path = safe_path(workspace, args.path)
        if args.command == "list-tree":
            if not path.is_dir():
                raise ValueError("path is not a directory")
            items = []
            for child in sorted(path.rglob("*")):
                if child.is_symlink():
                    raise ValueError("symbolic links are forbidden")
                items.append(
                    {
                        "path": child.relative_to(workspace).as_posix(),
                        "type": "directory" if child.is_dir() else "file",
                    }
                )
            payload = {"ok": True, "items": items}
        elif args.command == "read-text":
            if path.suffix.lower() not in {".csv", ".md", ".txt", ".json"} or not path.is_file():
                raise ValueError("read-text only supports workspace text files")
            payload = {"ok": True, "path": args.path, "text": path.read_text(encoding="utf-8")}
        else:
            if not path.is_file():
                raise ValueError("path is not a file")
            payload = {"ok": True, "path": args.path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
