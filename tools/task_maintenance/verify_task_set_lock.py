#!/usr/bin/env python3
"""Create or verify a content lock for one named task set."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from harnessbench.task_sets import load_task_set, task_ids_sha256  # noqa: E402
from run_benchmark import task_definition_sha256  # noqa: E402


def package_paths(task_dir: Path) -> list[Path]:
    """Return package paths in the same bytewise POSIX order on every OS."""
    return sorted(
        task_dir.rglob("*"),
        key=lambda path: path.relative_to(task_dir).as_posix(),
    )


def package_sha256(task_dir: Path) -> str:
    """Hash one complete package with the runner's snapshot exclusions."""
    digest = hashlib.sha256()
    for path in package_paths(task_dir):
        relative = path.relative_to(task_dir)
        if (
            "__pycache__" in relative.parts
            or path.suffix == ".pyc"
            or path.name in {".DS_Store", "llm_rubric.py"}
        ):
            continue
        if path.is_symlink():
            raise RuntimeError(f"task package must not contain symlinks: {path}")
        if not path.is_file():
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_lock(
    task_set_name: str,
    *,
    suite_root: Path = ROOT,
) -> dict[str, object]:
    tasks_dir = suite_root / "tasks"
    known = [path.parent.name for path in tasks_dir.glob("*/task.yaml")]
    task_set = load_task_set(
        suite_root / "catalog",
        task_set_name,
        known_task_ids=known,
    )
    packages: dict[str, dict[str, str]] = {}
    for task_id in task_set.task_ids:
        task_dir = tasks_dir / task_id
        packages[task_id] = {
            "task_definition_sha256": task_definition_sha256(task_dir),
            "complete_package_sha256": package_sha256(task_dir),
        }
    return {
        "schema_version": 1,
        "task_set": task_set.name,
        "task_count": task_set.task_count,
        "task_set_manifest_sha256": task_set.manifest_sha256,
        "task_ids_sha256": task_ids_sha256(task_set.task_ids),
        "hash_policy": {
            "task_definition": "runner_v1_excludes_reference_cache_and_llm_rubric",
            "complete_package": "snapshot_v1_includes_hidden_files_excludes_cache_and_llm_rubric",
        },
        "tasks": packages,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-set", required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument(
        "--suite-root",
        type=Path,
        default=ROOT,
        help="suite directory containing tasks/ and catalog/",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    suite_root = args.suite_root.expanduser().resolve()
    actual = build_lock(args.task_set, suite_root=suite_root)
    lock_path = args.lock if args.lock.is_absolute() else suite_root / args.lock
    if args.write:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(actual, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote={lock_path}")
        return 0

    try:
        expected = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid lock {lock_path}: {exc}", file=sys.stderr)
        return 2
    if expected != actual:
        expected_tasks = expected.get("tasks", {}) if isinstance(expected, dict) else {}
        actual_tasks = actual["tasks"]
        changed = sorted(
            task_id
            for task_id in set(expected_tasks) | set(actual_tasks)
            if expected_tasks.get(task_id) != actual_tasks.get(task_id)
        )
        print(
            "task-set lock mismatch; changed_or_missing=" + ",".join(changed),
            file=sys.stderr,
        )
        return 1
    print(
        f"verified task_set={args.task_set} tasks={actual['task_count']} "
        f"manifest={actual['task_set_manifest_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
