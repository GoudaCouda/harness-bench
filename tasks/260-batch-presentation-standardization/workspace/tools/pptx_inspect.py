#!/usr/bin/env python3
"""Inspect one synthetic PPTX without modifying the workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from pptx_core import PptxContractError, inspect_pptx, resolve_inside  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--input", required=True, help="工作区内相对路径")
    args = parser.parse_args()
    try:
        workspace = args.workspace.resolve(strict=True)
        source = resolve_inside(workspace, args.input)
        allowed = workspace / "inputs" / "decks"
        source.resolve(strict=True).relative_to(allowed.resolve(strict=True))
        result = inspect_pptx(source)
    except (OSError, ValueError, PptxContractError) as exc:
        print(json.dumps({"status": "error", "code": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "deck": result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

