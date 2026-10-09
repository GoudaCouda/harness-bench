#!/usr/bin/env python3
"""Deterministic CSV writer with a fixed public register schema."""

from __future__ import annotations

import argparse
import csv
import json
import os
import stat
from pathlib import Path


FIELDS = [
    "person_id",
    "name",
    "project_resume_status",
    "project_resume_file",
    "project_resume_source_attachment_id",
    "compliance_declaration_status",
    "compliance_declaration_file",
    "compliance_declaration_source_attachment_id",
    "overall_status",
    "reminder_status",
]
MAX_ROWS_JSON_BYTES = 64 * 1024
MAX_ROWS = 64
MAX_CELL_CHARS = 4096


def safe_workspace_path(workspace: Path, value: str, first_part: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != first_part:
        raise ValueError("path is outside the allowed workspace scope")
    current = workspace
    for part in relative.parts[:-1]:
        current = current / part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ValueError("path parent is not a real directory")
    target = current / relative.parts[-1]
    if target.exists() and target.is_symlink():
        raise ValueError("symbolic links are forbidden")
    target = target.resolve(strict=False)
    target.relative_to(workspace)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(prog="spreadsheet_cli")
    parser.add_argument("write-register")
    parser.add_argument("--rows-json", required=True)
    parser.add_argument("--output", default="outputs/material_register.csv")
    try:
        args = parser.parse_args()
        value = os.environ.get("CASE20_WORKSPACE")
        if not value:
            raise ValueError("CASE20_WORKSPACE must be set")
        workspace = Path(value).resolve(strict=True)
        output = safe_workspace_path(workspace, args.output, "outputs")
        if output.exists() or output.is_symlink():
            raise FileExistsError("refusing to overwrite register output")
        if len(args.rows_json.encode("utf-8")) > MAX_ROWS_JSON_BYTES:
            raise ValueError("rows JSON exceeds the published request bound")
        rows = json.loads(args.rows_json)
        if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
            raise ValueError("rows JSON must be a non-empty array")
        normalized = []
        for row in rows:
            if not isinstance(row, dict) or list(row.keys()) != FIELDS:
                raise ValueError("every row must have the fixed fields in the published order")
            if any(
                not isinstance(row[field], str) or len(row[field]) > MAX_CELL_CHARS
                for field in FIELDS
            ):
                raise ValueError("all register cells must be strings")
            normalized.append(row)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(normalized)
        print(json.dumps({"ok": True, "output": args.output, "row_count": len(normalized)}, sort_keys=True))
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
