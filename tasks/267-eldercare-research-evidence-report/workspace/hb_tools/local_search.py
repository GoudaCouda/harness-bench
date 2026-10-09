#!/usr/bin/env python3
"""Literal, offline search over the fixed case corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    corpus = args.workspace.resolve(strict=True) / "input" / "corpus"
    query = args.query.casefold()
    if not query.strip():
        raise ValueError("query must be non-empty")
    matches: list[dict[str, object]] = []
    for path in sorted(corpus.iterdir()):
        if not path.is_file() or path.is_symlink():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if query in line.casefold():
                matches.append(
                    {
                        "path": path.relative_to(args.workspace).as_posix(),
                        "line": line_number,
                        "text": line,
                    }
                )
                if len(matches) >= args.limit:
                    print(json.dumps({"matches": matches}, ensure_ascii=False))
                    return 0
    print(json.dumps({"matches": matches}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
