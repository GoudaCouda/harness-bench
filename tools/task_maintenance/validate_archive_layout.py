#!/usr/bin/env python3
"""Validate the physical active/archive partition for the current release."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_ROOT = ROOT / "tasks"
ARCHIVE_ROOT = ROOT / "archived_tasks"
CATALOG_ROOT = ROOT / "catalog"


def _manifest_ids(name: str, *, expected_count: int) -> list[str]:
    path = CATALOG_ROOT / f"{name}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("task_count") != expected_count:
        raise RuntimeError(f"{path} must declare task_count={expected_count}")
    task_ids = raw.get("task_ids")
    if (
        not isinstance(task_ids, list)
        or len(task_ids) != expected_count
        or len(set(task_ids)) != expected_count
        or not all(isinstance(task_id, str) and task_id for task_id in task_ids)
    ):
        raise RuntimeError(f"{path} has an invalid task_ids list")
    return task_ids


def _disk_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for task_yaml in sorted(root.glob("*/task.yaml")):
        directory_id = task_yaml.parent.name
        raw = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
        if raw.get("task_id") != directory_id:
            raise RuntimeError(
                f"task_id/directory mismatch: {task_yaml} declares {raw.get('task_id')!r}"
            )
        ids.add(directory_id)
    return ids


def main() -> int:
    release_path = CATALOG_ROOT / "release.yaml"
    release = yaml.safe_load(release_path.read_text(encoding="utf-8")) or {}
    active_name = str(release.get("active_manifest") or "")
    archive_name = str(release.get("archive_manifest") or "")
    historical_count = int(release.get("historical_prefix_count") or 0)
    active_raw = yaml.safe_load(
        (CATALOG_ROOT / f"{active_name}.yaml").read_text(encoding="utf-8")
    )
    archive_raw = yaml.safe_load(
        (CATALOG_ROOT / f"{archive_name}.yaml").read_text(encoding="utf-8")
    )
    active_count = int(active_raw.get("task_count") or 0)
    archive_count = int(archive_raw.get("task_count") or 0)
    active_manifest = set(_manifest_ids(active_name, expected_count=active_count))
    archive_manifest = set(_manifest_ids(archive_name, expected_count=archive_count))
    active_disk = _disk_ids(ACTIVE_ROOT)
    archive_disk = _disk_ids(ARCHIVE_ROOT)

    errors: list[str] = []
    if active_manifest != active_disk:
        errors.append(
            "active mismatch: "
            f"missing={sorted(active_manifest - active_disk)} "
            f"extra={sorted(active_disk - active_manifest)}"
        )
    if archive_manifest != archive_disk:
        errors.append(
            "archive mismatch: "
            f"missing={sorted(archive_manifest - archive_disk)} "
            f"extra={sorted(archive_disk - archive_manifest)}"
        )
    overlap = active_disk & archive_disk
    if overlap:
        errors.append(f"active/archive overlap={sorted(overlap)}")
    all_ids = active_disk | archive_disk
    prefix_counts: dict[str, int] = {}
    for task_id in all_ids:
        prefix = task_id.split("-", 1)[0]
        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    duplicate_prefixes = sorted(
        prefix for prefix, count in prefix_counts.items() if count != 1
    )
    if duplicate_prefixes:
        errors.append(f"numeric prefix duplication={duplicate_prefixes}")
    prefixes = set(prefix_counts)
    expected_prefixes = {
        f"{number:03d}" for number in range(1, historical_count + 1)
    }
    if prefixes != expected_prefixes:
        errors.append(
            "historical ID coverage mismatch: "
            f"missing={sorted(expected_prefixes - prefixes)} "
            f"extra={sorted(prefixes - expected_prefixes)}"
        )
    if len(all_ids) != historical_count:
        errors.append(
            f"expected {historical_count} preserved packages, found {len(all_ids)}"
        )

    print(f"active_manifest={active_name}")
    print(f"archive_manifest={archive_name}")
    print(f"active_tasks={len(active_disk)}")
    print(f"archived_tasks={len(archive_disk)}")
    print(f"errors={len(errors)}")
    for error in errors:
        print(f"ERROR {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
