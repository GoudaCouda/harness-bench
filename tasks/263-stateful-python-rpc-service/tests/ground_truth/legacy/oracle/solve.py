#!/usr/bin/env python3
"""Install the hidden reference service into a freshly reset workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    source = args.case_root.resolve() / "oracle" / "service.py"
    destination = args.workspace.resolve() / "submission" / "service.py"
    if not destination.is_file() or destination.is_symlink():
        raise ValueError("workspace must be a fresh case_09 reset")
    shutil.copyfile(source, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
