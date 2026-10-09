#!/usr/bin/env python3
"""Trusted feasible solution for environment validation only."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


EXPECTED = ("market_brief.pptx", "project_update.pptx", "service_review.pptx")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.work_root.resolve(strict=True)
    tool = workspace / "tools" / "pptx_standardize.py"
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    results: list[dict[str, object]] = []
    for name in EXPECTED:
        command = [
            sys.executable,
            tool.as_posix(),
            "--workspace",
            workspace.as_posix(),
            "--input",
            f"inputs/decks/{name}",
            "--output",
            f"outputs/standardized/{name}",
        ]
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
            env=env,
        )
        if completed.returncode != 0:
            print(json.dumps({"status": "error", "code": "oracle_tool_failed", "file": name}))
            return 2
        results.append(json.loads(completed.stdout))
    print(json.dumps({"status": "ok", "outputs": results}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

