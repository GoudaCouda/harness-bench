#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="只读解析工作区内的 Markdown 制度文件")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve(strict=True)
    candidate = (workspace / args.path).resolve(strict=True)
    candidate.relative_to(workspace / "input")
    if candidate.is_symlink() or candidate.suffix != ".md":
        raise ValueError("only regular Markdown input files are readable")
    sections: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line_number, raw in enumerate(candidate.read_text(encoding="utf-8").splitlines(), 1):
        if raw.startswith("## "):
            current = {"heading": raw[3:], "line": line_number, "paragraphs": []}
            sections.append(current)
        elif raw.strip() and current is not None:
            paragraphs = current["paragraphs"]
            assert isinstance(paragraphs, list)
            paragraphs.append({"line": line_number, "text": raw.strip()})
    print(json.dumps({"path": args.path, "sections": sections}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

