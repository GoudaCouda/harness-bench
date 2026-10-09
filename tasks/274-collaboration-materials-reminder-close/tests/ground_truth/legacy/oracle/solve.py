#!/usr/bin/env python3
"""Hidden feasible solver for case_20 validation only."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(command: list[str], environment: dict[str, str]) -> None:
    completed = subprocess.run(
        command,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"tool failed: {Path(command[1]).name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    case_root = args.case_root.resolve(strict=True)
    work_root = args.work_root.resolve(strict=True)
    workspace = work_root / "workspace"
    socket_path = work_root / "service.sock"
    reference = json.loads((case_root / "oracle/reference_state.json").read_text(encoding="utf-8"))
    environment = os.environ.copy()
    environment.update(
        {
            "CASE20_WORKSPACE": str(workspace),
            "CASE20_SERVICE_SOCKET": str(socket_path),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    collab = case_root / "environment/tools/collab_cli.py"
    spreadsheet = case_root / "environment/tools/spreadsheet_cli.py"
    for item in reference["archive_files"]:
        run(
            [
                sys.executable,
                str(collab),
                "download-attachment",
                "--attachment-id",
                item["attachment_id"],
                "--destination",
                item["path"],
            ],
            environment,
        )
    ordered_rows = [
        {field: row[field] for field in reference["register_fields"]}
        for row in reference["register_rows"]
    ]
    run(
        [
            sys.executable,
            str(spreadsheet),
            "write-register",
            "--rows-json",
            json.dumps(ordered_rows, ensure_ascii=False),
            "--output",
            "outputs/material_register.csv",
        ],
        environment,
    )
    for item in reference["reminders"]:
        run(
            [
                sys.executable,
                str(collab),
                "send-reminder",
                "--recipient-id",
                item["recipient_id"],
                "--body",
                item["body"],
            ],
            environment,
        )
    print(json.dumps({"ok": True, "archive_count": 8, "register_rows": 6, "reminder_count": 3}, sort_keys=True))


if __name__ == "__main__":
    main()
