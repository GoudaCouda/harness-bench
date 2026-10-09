#!/usr/bin/env python3
"""Generate the deterministic initial workspace manifest for case_20."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from state import canonical_json_bytes, sha256_file, source_projection_from_seed


def main() -> None:
    case_root = Path(__file__).resolve().parents[1]
    files = []
    seed_root = case_root / "fixtures/workspace_seed"
    for path in sorted(seed_root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            files.append(
                {
                    "mode": "0o444",
                    "path": path.relative_to(seed_root).as_posix(),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    source = source_projection_from_seed(case_root)
    payload = {
        "schema_version": "case20_workspace_manifest_v1",
        "visible_seed_files": files,
        "empty_directories": ["archive", "outputs"],
        "runtime_directory_modes": {
            "archive": "0o700",
            "inputs": "0o555",
            "outputs": "0o700",
            "workspace": "0o700"
        },
        "source_projection_sha256": hashlib.sha256(canonical_json_bytes(source)).hexdigest(),
        "initial_action_counts": {"downloads": 0, "reminders": 0},
        "candidate_mount_contract": {
            "path": "environment/candidate_mounts.json",
            "sha256": sha256_file(case_root / "environment/candidate_mounts.json"),
        },
        "tool_contract": {
            "path": "environment/tool_contract.json",
            "sha256": sha256_file(case_root / "environment/tool_contract.json"),
        },
    }
    (case_root / "environment/workspace_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
