#!/usr/bin/env python3
"""Reset the case workspace to its immutable fixture state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from state_model import create_database, state_hash_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=Path)
    args = parser.parse_args()
    args.workspace.mkdir(parents=True, exist_ok=True)
    db_path = args.workspace / "state.sqlite"
    create_database(db_path, args.catalog, args.seed)
    payload = {
        "status": "reset",
        "database": db_path.name,
        "initial_state_sha256": state_hash_path(db_path),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
