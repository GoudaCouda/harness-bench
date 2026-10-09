#!/usr/bin/env python3
"""Apply the visible deterministic style map to one input deck."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from pptx_core import (  # noqa: E402
    PptxContractError,
    resolve_inside,
    sha256_file,
    standardize_pptx,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--style-map", default="inputs/style_map.json")
    args = parser.parse_args()
    try:
        workspace = args.workspace.resolve(strict=True)
        source = resolve_inside(workspace, args.input)
        destination = resolve_inside(workspace, args.output)
        style_path = resolve_inside(workspace, args.style_map)
        source.resolve(strict=True).relative_to((workspace / "inputs/decks").resolve(strict=True))
        destination.parent.resolve(strict=True).relative_to(
            (workspace / "outputs/standardized").resolve(strict=True)
        )
        style_path.resolve(strict=True).relative_to((workspace / "inputs").resolve(strict=True))
        style_map = json.loads(style_path.read_text(encoding="utf-8"))
        expected = style_map["batch_files"]
        if not isinstance(expected, dict):
            raise PptxContractError("batch_contract_invalid")
        source_name = source.name
        if expected.get(source_name) != destination.name:
            raise PptxContractError("batch_path_not_declared")
        source_hashes = style_map.get("input_sha256", {})
        if source_hashes.get(source_name) != sha256_file(source):
            raise PptxContractError("input_hash_mismatch")
        standardize_pptx(source, destination, style_map)
        result = {"status": "ok", "output": args.output, "sha256": sha256_file(destination)}
    except (KeyError, OSError, ValueError, json.JSONDecodeError, PptxContractError) as exc:
        print(json.dumps({"status": "error", "code": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

