#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from datetime import datetime


def fail(message: str) -> None:
    raise SystemExit(message)


if sys.version_info[:2] != (3, 12):
    fail(
        "task 078 requires CPython 3.12 in the agent image; "
        f"found {sys.version_info.major}.{sys.version_info.minor}"
    )

parser = argparse.ArgumentParser()
commands = parser.add_subparsers(dest="command", required=True)
commands.add_parser("inspect")
commands.add_parser("verify")
if parser.parse_args(["verify"]).command != "verify":
    fail("argparse subcommand capability probe failed")

rows = list(
    csv.DictReader(
        io.StringIO(
            "status,recorded_at\n"
            "approved,2026-08-01T10:00:00Z\n"
        )
    )
)
recorded_at = datetime.fromisoformat(
    rows[0]["recorded_at"].replace("Z", "+00:00")
)
if rows[0]["status"] != "approved" or recorded_at.tzinfo is None:
    fail("CSV/timezone capability probe failed")

probe = subprocess.run(
    [
        sys.executable,
        "-B",
        "-c",
        "import argparse,csv,datetime,json,pathlib; print('ok')",
    ],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    fail(f"stdlib subprocess probe failed: {probe.stderr.strip()}")

print(
    json.dumps(
        {
            "python": "3.12",
            "stdlib": ["argparse", "csv", "datetime", "json", "pathlib"],
            "timezone_aware": True,
        },
        sort_keys=True,
    )
)
