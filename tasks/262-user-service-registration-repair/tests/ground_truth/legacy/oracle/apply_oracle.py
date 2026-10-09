from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the hidden case_08 reference change")
    parser.add_argument("--workspace", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    workspace = args.workspace.resolve(strict=True)
    destination = workspace / "nami_service" / "users.py"
    if not destination.is_file() or destination.is_symlink():
        raise ValueError("workspace does not contain the expected source file")
    source = Path(__file__).resolve().parent / "reference" / "users.py"
    shutil.copyfile(source, destination)
    print(json.dumps({"schema_version": "case08_oracle_apply_v1", "applied": True}))
