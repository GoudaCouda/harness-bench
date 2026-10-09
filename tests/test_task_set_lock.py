from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "task_maintenance" / "verify_task_set_lock.py"
SPEC = importlib.util.spec_from_file_location("verify_task_set_lock", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_current_standard274_release_matches_active_tree() -> None:
    import yaml

    current = yaml.safe_load((ROOT / "catalog/standard274.yaml").read_text())
    archive = yaml.safe_load((ROOT / "catalog/archive0.yaml").read_text())
    active_disk = {path.parent.name for path in (ROOT / "tasks").glob("*/task.yaml")}
    archive_disk = set()
    archive_root = ROOT / "archived_tasks"
    if archive_root.is_dir():
        archive_disk = {
            path.parent.name for path in archive_root.glob("*/task.yaml")
        }
    current_ids = set(current["task_ids"])
    archive_ids = set(archive["task_ids"])

    assert len(current_ids) == current["task_count"] == 274
    assert len(archive_ids) == archive["task_count"] == 0
    assert not current_ids & archive_ids
    assert current_ids == active_disk
    assert archive_ids == archive_disk
    assert len(active_disk | archive_disk) == 274


def test_package_hash_changes_when_hidden_content_changes(tmp_path: Path) -> None:
    task = tmp_path / "task"
    (task / "tests/reference").mkdir(parents=True)
    (task / "workspace").mkdir()
    (task / "workspace/input.txt").write_text("input\n")
    (task / "tests/reference/output.txt").write_text("one\n")
    before = MODULE.package_sha256(task)
    (task / "tests/reference/output.txt").write_text("two\n")
    assert MODULE.package_sha256(task) != before


def test_package_hash_uses_platform_independent_posix_path_order(
    tmp_path: Path,
) -> None:
    task = tmp_path / "task"
    task.mkdir()
    for relative in ("a.txt", "A.txt", "nested/Z.txt", "nested/b.txt"):
        path = task / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")

    expected = [
        "A.txt",
        "a.txt",
        "nested",
        "nested/Z.txt",
        "nested/b.txt",
    ]
    ordered = MODULE.package_paths(task)
    assert [path.relative_to(task).as_posix() for path in ordered] == expected

    digest = hashlib.sha256()
    for relative in ("A.txt", "a.txt", "nested/Z.txt", "nested/b.txt"):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((task / relative).read_bytes())
        digest.update(b"\0")
    assert MODULE.task_definition_sha256(task) == digest.hexdigest()
