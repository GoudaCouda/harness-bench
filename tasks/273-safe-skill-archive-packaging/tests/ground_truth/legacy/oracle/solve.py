from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType


def load_skillctl(case_root: Path) -> ModuleType:
    path = case_root / "environment/skillctl.py"
    spec = importlib.util.spec_from_file_location("case19_skillctl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("skillctl_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def solve(case_root: Path, workspace: Path) -> Path:
    skillctl = load_skillctl(case_root)
    source = workspace / "input/calendar_briefing_skill"
    output = workspace / "output/calendar_briefing_skill.zip"
    manifest_path = workspace / ".manifest.build.json"
    records = skillctl.expected_file_records(source)
    manifest = {
        "entrypoint": "scripts/main.py",
        "files": records,
        "package_name": "calendar_briefing_skill",
        "schema_version": "skill_package_manifest_v1",
        "version": "1.2.0",
    }
    manifest_path.write_bytes(skillctl.canonical_manifest_bytes(manifest))
    try:
        skillctl.write_zip(source, manifest_path, output)
    finally:
        if manifest_path.exists() and not manifest_path.is_symlink():
            manifest_path.unlink()
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    output = solve(args.case_root, args.workspace)
    print(json.dumps({"status": "ok", "output": str(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
