#!/usr/bin/env python3
"""Reset an isolated case_20 runtime and run the trusted sidecar as PID 1."""

from __future__ import annotations

import argparse
from pathlib import Path

from reset import reset
from service import serve


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    reset(args.case_root, args.work_root)
    serve(args.work_root)


if __name__ == "__main__":
    main()
