"""Pure-filesystem tests for case_10's editable-to-frozen handoff."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

import pytest


ENVIRONMENT_ROOT = Path(__file__).resolve().parents[1] / "environment"
sys.path.insert(0, os.fspath(ENVIRONMENT_ROOT))

import freeze_submission as freeze  # noqa: E402
import prepare_agent_workspace as prepare  # noqa: E402


def _identity() -> tuple[int, int]:
    return os.getuid(), os.getgid()


def _prepare(allowed_root: Path, workspace: Path) -> dict[str, object]:
    uid, gid = _identity()
    return prepare.prepare_agent_workspace(
        workspace=workspace,
        allowed_root=allowed_root,
        agent_uid=uid,
        agent_gid=gid,
        controller_uid=uid,
        controller_gid=gid,
    )


def _freeze(allowed_root: Path, workspace: Path, submission: Path) -> dict[str, object]:
    uid, gid = _identity()
    return freeze.freeze_submission(
        workspace=workspace,
        submission=submission,
        allowed_root=allowed_root,
        owner_uid=uid,
        owner_gid=gid,
        agent_stopped=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


def test_prepare_edit_freeze_normal_flow(tmp_path: Path) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    submission = allowed_root / "submission"
    prepared = _prepare(allowed_root, workspace)

    assert prepared["initial_state_sha256"] == (
        "b3c971a8d53f93661cbdb9932dfc6cd968b61828f74db5b8509adb6ceeb61d08"
    )
    assert stat.S_IMODE(os.lstat(workspace).st_mode) == 0o555
    assert stat.S_IMODE(os.lstat(workspace / "src").st_mode) == 0o755
    assert stat.S_IMODE(os.lstat(workspace / "src/process.js").st_mode) == 0o644
    assert stat.S_IMODE(os.lstat(workspace / "task.md").st_mode) == 0o444

    with (workspace / "src/process.js").open("a", encoding="utf-8") as handle:
        handle.write("\n// teacher edit\n")
    frozen = _freeze(allowed_root, workspace, submission)

    assert frozen["candidate_tree_sha256"] == frozen["submission_tree_sha256"]
    assert stat.S_IMODE(os.lstat(submission).st_mode) == 0o555
    assert all(
        stat.S_IMODE(os.lstat(path).st_mode) == (0o555 if path.is_dir() else 0o444)
        for path in submission.rglob("*")
    )
    assert (submission / "src/process.js").read_text(encoding="utf-8").endswith(
        "// teacher edit\n"
    )


def test_polluted_same_path_is_atomically_reset(tmp_path: Path) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    _prepare(allowed_root, workspace)
    workspace.chmod(0o755)
    (workspace / "garbage.txt").write_text("pollution", encoding="utf-8")
    (workspace / "task.md").chmod(0o644)
    (workspace / "task.md").write_text("tampered", encoding="utf-8")
    (workspace / "src/extra.js").write_text("extra", encoding="utf-8")

    result = _prepare(allowed_root, workspace)

    declared = json.loads(prepare.WORKSPACE_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_files = {item["path"] for item in declared["files"]}
    assert {path for path in _paths(workspace) if (workspace / path).is_file()} == expected_files
    assert result["initial_state_sha256"] == declared["initial_state_sha256"]
    assert (workspace / "task.md").read_bytes() == (prepare.FIXTURE_ROOT / "task.md").read_bytes()


def test_prepare_rejects_path_escape(tmp_path: Path) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    with pytest.raises(prepare.WorkspaceContractError, match="escapes allowed root"):
        _prepare(allowed_root, tmp_path / "outside")


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "fifo", "extra_file"])
def test_freeze_rejects_unsafe_or_extra_entries(tmp_path: Path, attack: str) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    submission = allowed_root / "submission"
    _prepare(allowed_root, workspace)
    target = workspace / "src" / "forbidden"
    if attack == "symlink":
        target.symlink_to("process.js")
        expected = "symlink"
    elif attack == "hardlink":
        os.link(workspace / "task.md", target)
        expected = "hardlink"
    elif attack == "fifo":
        os.mkfifo(target)
        expected = "special"
    else:
        target.write_text("extra", encoding="utf-8")
        expected = "inventory"

    with pytest.raises(prepare.WorkspaceContractError, match=expected):
        _freeze(allowed_root, workspace, submission)
    assert not submission.exists()


def test_freeze_rejects_protected_file_modification(tmp_path: Path) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    submission = allowed_root / "submission"
    _prepare(allowed_root, workspace)
    protected = workspace / "package.json"
    protected.chmod(0o644)
    protected.write_text("{}\n", encoding="utf-8")

    with pytest.raises(prepare.WorkspaceContractError, match="protected"):
        _freeze(allowed_root, workspace, submission)
    assert not submission.exists()


def test_freeze_requires_stopped_agent_assertion(tmp_path: Path) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    _prepare(allowed_root, workspace)
    uid, gid = _identity()

    with pytest.raises(prepare.WorkspaceContractError, match="stopped-agent"):
        freeze.freeze_submission(
            workspace=workspace,
            submission=allowed_root / "submission",
            allowed_root=allowed_root,
            owner_uid=uid,
            owner_gid=gid,
            agent_stopped=False,
        )


def test_concurrent_freeze_fails_closed_on_lock(tmp_path: Path) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    _prepare(allowed_root, workspace)
    lock_path = allowed_root / ".case10-agent-workspace.lock"
    descriptor = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(prepare.WorkspaceContractError, match="already held"):
            _freeze(allowed_root, workspace, allowed_root / "submission")
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def test_source_change_during_freeze_keeps_old_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    submission = allowed_root / "submission"
    _prepare(allowed_root, workspace)
    _freeze(allowed_root, workspace, submission)
    old_hash = _sha256(submission / "src/process.js")
    original_copy = freeze.copy_admitted_tree

    def copy_then_mutate(*args: object, **kwargs: object) -> None:
        original_copy(*args, **kwargs)
        with (workspace / "src/process.js").open("a", encoding="utf-8") as handle:
            handle.write("\n// concurrent mutation\n")

    monkeypatch.setattr(freeze, "copy_admitted_tree", copy_then_mutate)
    with pytest.raises(prepare.WorkspaceContractError, match="changed during freeze"):
        _freeze(allowed_root, workspace, submission)

    assert _sha256(submission / "src/process.js") == old_hash
    assert not list(allowed_root.glob(".submission.freeze.*"))


def test_freeze_publish_interruption_preserves_previous_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    submission = allowed_root / "submission"
    _prepare(allowed_root, workspace)
    _freeze(allowed_root, workspace, submission)
    old_hash = _sha256(submission / "src/process.js")
    with (workspace / "src/process.js").open("a", encoding="utf-8") as handle:
        handle.write("\n// next version\n")

    def interrupted(_stage: Path, _destination: Path) -> None:
        raise prepare.WorkspaceContractError("injected staging interruption")

    monkeypatch.setattr(freeze, "_atomic_publish_directory", interrupted)
    with pytest.raises(prepare.WorkspaceContractError, match="staging interruption"):
        _freeze(allowed_root, workspace, submission)

    assert _sha256(submission / "src/process.js") == old_hash
    assert not list(allowed_root.glob(".submission.freeze.*"))


def test_prepare_publish_interruption_preserves_existing_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed_root = tmp_path / "managed"
    allowed_root.mkdir()
    workspace = allowed_root / "agent_workspace"
    _prepare(allowed_root, workspace)
    with (workspace / "src/process.js").open("a", encoding="utf-8") as handle:
        handle.write("\n// existing workspace marker\n")
    old_hash = _sha256(workspace / "src/process.js")

    def interrupted(_stage: Path, _destination: Path) -> None:
        raise prepare.WorkspaceContractError("injected prepare interruption")

    monkeypatch.setattr(prepare, "_atomic_publish_directory", interrupted)
    with pytest.raises(prepare.WorkspaceContractError, match="prepare interruption"):
        _prepare(allowed_root, workspace)

    assert _sha256(workspace / "src/process.js") == old_hash
    assert not list(allowed_root.glob(".agent-workspace.prepare.*"))
