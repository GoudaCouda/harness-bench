#!/usr/bin/env python3
"""Install the trusted reference source into an already reset submission."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


CASE_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True)
    args = parser.parse_args()
    destination = Path(args.submission).resolve()
    if destination.name != "submission" or destination.is_symlink() or not destination.is_dir():
        raise SystemExit("submission must be an existing non-symlink directory named submission")
    source = CASE_ROOT / "oracle" / "solution.js"
    target = destination / "src" / "process.js"
    if target.is_symlink() or not target.parent.is_dir():
        raise SystemExit("invalid submission layout")
    shutil.copyfile(source, target)
    target.chmod(0o644)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
