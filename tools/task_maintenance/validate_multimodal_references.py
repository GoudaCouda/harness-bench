#!/usr/bin/env python3
"""Grade every multimodal reference and untouched workspace in the browser.

A task passes when its reference scores 1.0 with task success and its
untouched starter workspace does not succeed. Requires Python Playwright with
Chromium installed (``python -m playwright install --with-deps chromium``).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

from common import load_task_metadata, score_task_workspace


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE_ROOT = ROOT / "suites" / "multimodal26"


def task_ids(suite_root: Path) -> list[str]:
    release = yaml.safe_load((suite_root / "catalog" / "release.yaml").read_text())
    manifest = suite_root / "catalog" / f"{release['active_manifest']}.yaml"
    return list(yaml.safe_load(manifest.read_text())["task_ids"])


def grade(task_dir: Path, metadata: dict, with_reference: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="harnessbench-multimodal-") as tmp:
        workspace = Path(tmp) / "workspace"
        shutil.copytree(task_dir / "workspace", workspace, symlinks=True)
        if with_reference:
            shutil.copytree(
                task_dir / "tests" / "reference",
                workspace,
                dirs_exist_ok=True,
                symlinks=True,
            )
        return score_task_workspace(task_dir, metadata, workspace)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument(
        "--require-reference",
        action="store_true",
        help="fail tasks that do not ship tests/reference",
    )
    args = parser.parse_args()
    suite_root = args.suite_root.expanduser().resolve()

    failed = skipped = 0
    selected = task_ids(suite_root)
    for task_id in selected:
        task_dir = (suite_root / "tasks" / task_id).resolve()
        metadata = load_task_metadata(task_dir / "task.yaml")
        if not (task_dir / "tests" / "reference").is_dir():
            skipped += 1
            print(f"{'FAIL' if args.require_reference else 'SKIP'} {task_id}: no tests/reference")
            continue
        reference = grade(task_dir, metadata, with_reference=True)
        untouched = grade(task_dir, metadata, with_reference=False)
        problems = []
        if reference.get("outcome_score") != 1.0 or reference.get("task_success") is not True:
            problems.append(
                f"reference={reference.get('outcome_score')} "
                f"success={reference.get('task_success')}"
            )
        if untouched.get("task_success") is not False:
            problems.append(f"untouched_success={untouched.get('task_success')}")
        failed += bool(problems)
        print(
            f"{'FAIL' if problems else 'PASS'} {task_id}: "
            f"reference={reference.get('outcome_score')}, "
            f"untouched={untouched.get('outcome_score')}"
            + (f" [{'; '.join(problems)}]" if problems else "")
        )

    if args.require_reference:
        failed += skipped
    print(f"tasks={len(selected)} failed={failed} without_reference={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
