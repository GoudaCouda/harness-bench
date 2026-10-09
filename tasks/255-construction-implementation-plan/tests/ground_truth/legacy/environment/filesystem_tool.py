"""Read-only workspace inspection tool used by the future agent harness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def safe_path(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    candidate.relative_to(workspace.resolve())
    if not relative.startswith("inputs/"):
        raise ValueError("filesystem tool may only read workspace inputs")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()
    path = safe_path(args.workspace, args.path)
    payload = path.read_bytes()
    result = {
        "path": args.path,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "text": payload.decode("utf-8") if path.suffix.lower() in {".md", ".json", ".csv"} else None,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
