#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


CASE_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve(strict=True)
    output = workspace / "output" / "review_report.json"
    output.parent.mkdir(exist_ok=True)
    shutil.copyfile(CASE_DIR / "oracle" / "reference_report.json", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

