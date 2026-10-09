#!/usr/bin/env python3
"""Install the hidden reference document into a reset workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    source = args.case_root.resolve(strict=True) / "oracle" / "reference_report.md"
    output = args.workspace.resolve(strict=True) / "output" / "养老行业研究报告.md"
    if any(output.parent.iterdir()):
        raise ValueError("output directory must be empty")
    shutil.copyfile(source, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
