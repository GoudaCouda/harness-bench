#!/usr/bin/env python3
"""Validate config and replay the public routing truth table offline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "testdata/public_cases.json",
    )
    args = parser.parse_args()
    validator = os.environ.get("ALERTMANAGER_VALIDATOR", "").strip()
    if not validator:
        raise SystemExit(
            "ALERTMANAGER_VALIDATOR is unset; load the trusted ALERTMANAGER_ENV first"
        )
    subprocess.run(
        [
            validator,
            "check-config",
            str(args.config),
            "--utf8-strict",
        ],
        check=True,
    )
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    for case in cases["routing"]:
        labels = [f"{key}={value}" for key, value in case["labels"].items()]
        subprocess.run(
            [
                validator,
                "routes-test",
                str(args.config),
                *labels,
                f"--expect={','.join(case['receivers'])}",
            ],
            check=True,
        )
    print(f"validated {len(cases['routing'])} public routing cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
