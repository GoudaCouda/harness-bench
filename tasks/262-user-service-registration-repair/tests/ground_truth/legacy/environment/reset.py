from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from state_hash import workspace_sha256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset case_08 from immutable fixtures")
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    return parser.parse_args()


def reset(fixture_root: Path, workspace: Path) -> str:
    fixture = fixture_root.resolve(strict=True)
    target = workspace.resolve(strict=False)
    if target == Path("/") or len(target.parts) < 4:
        raise ValueError("workspace target is too broad")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ValueError("workspace target is unsafe")
        shutil.rmtree(target)
    shutil.copytree(fixture, target, symlinks=False)
    sys.path.insert(0, str(target))
    from nami_service.db import initialize_database

    initialize_database(target / "state" / "service.db")
    return workspace_sha256(target)


if __name__ == "__main__":
    arguments = parse_args()
    state_hash = reset(arguments.fixture_root, arguments.workspace)
    print(
        json.dumps(
            {"schema_version": "case08_reset_v1", "state_sha256": state_hash},
            sort_keys=True,
        )
    )
