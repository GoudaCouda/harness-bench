#!/usr/bin/env python3
"""Write the one permitted deliverable without exposing trusted artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    output = workspace / "output" / "养老行业研究报告.md"
    text = sys.stdin.read()
    if not text.strip():
        raise ValueError("document content must be non-empty")
    if len(text.encode("utf-8")) > 128 * 1024:
        raise ValueError("document exceeds 128 KiB")
    output.write_text(text, encoding="utf-8")
    print(json.dumps({"path": output.relative_to(workspace).as_posix(), "bytes": output.stat().st_size}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
